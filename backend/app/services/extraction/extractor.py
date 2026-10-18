import os
import re
import shutil
import threading
import time
import unicodedata
from collections import Counter, OrderedDict, namedtuple
from pathlib import Path

import cv2
import numpy as np
import pysrt
from Levenshtein import ratio
from numpy import average, dot, linalg
from PIL import Image

from app.services.extraction.area import SubtitleArea
from app.services.extraction.ocr import OcrRecogniser, get_coordinates
from app.services.extraction.settings import ExtractionConfig
from app.services.extraction.subtitle_ocr import start_subtitle_ocr
from app.services.extraction.subtitle_detect import SubtitleDetect
from app.services.extraction.tr import tr
from app.services.extraction import reformat
from app.services.extraction.paddle_model_config import PaddleModelConfig
from app.services.extraction.vsf_runner import VsfRunner
from app.services.unicode_io import imwrite_unicode


class VideoSubtitleExtractor:
    """视频硬字幕提取（CPU 部署版）"""

    def __init__(self, video_path, output_dir, sub_area=None, config: ExtractionConfig = None,
                 cancel_event: threading.Event = None, on_progress=None, on_log=None):
        self.lock = threading.RLock()
        self.config = config or ExtractionConfig()
        self.sub_area = sub_area
        self.cancel_event = cancel_event or threading.Event()
        self.on_progress = on_progress
        self.on_log = on_log

        self.video_path = video_path
        self.video_cap = cv2.VideoCapture(video_path)
        self.vd_name = Path(self.video_path).stem
        self.temp_output_dir = os.path.join(output_dir, 'temp', self.vd_name)
        self.output_dir = output_dir

        self.frame_count = self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.fps = self.video_cap.get(cv2.CAP_PROP_FPS) or 25
        self.frame_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        self.frame_output_dir = os.path.join(self.temp_output_dir, 'frames')
        self.subtitle_output_dir = os.path.join(self.temp_output_dir, 'subtitle')
        self.use_vsf = False
        self.vsf_subtitle = os.path.join(self.subtitle_output_dir, 'raw_vsf.srt')
        self.raw_subtitle_path = os.path.join(self.subtitle_output_dir, 'raw.txt')
        self.subtitle_output_path = os.path.join(output_dir, f'{self.vd_name}.srt')
        self.txt_output_path = os.path.join(output_dir, f'{self.vd_name}.txt')

        self.sub_detector = None
        self.ocr = None

        self.progress_total = 300
        self.progress_frame_extract = 0
        self.progress_ocr = 0
        self.progress_post = 0
        self.isFinished = False
        self.subtitle_ocr_thread = None
        self.subtitle_ocr_task_queue = None
        self.vsf_runner = None

    # ---------------- 对外主流程 ----------------

    def run(self):
        start_time = time.time()
        self.update_progress(ocr=0, frame_extract=0, post=0)
        self.log('-----------------------------')
        self.log(f"  识别语言：{self.config.language.value}  |  识别模式：{self.config.mode.value}  |  加速：CPU")
        self.log(f"  视频帧数：{self.frame_count}  |  帧率：{self.fps}")
        self.log(f"  DET: {os.path.basename(PaddleModelConfig(self.config.language.value, self.config.mode.value).DET_MODEL_PATH) if PaddleModelConfig(self.config.language.value, self.config.mode.value).DET_MODEL_PATH else '未找到'}"
                 f"  |  REC: {os.path.basename(PaddleModelConfig(self.config.language.value, self.config.mode.value).REC_MODEL_PATH) if PaddleModelConfig(self.config.language.value, self.config.mode.value).REC_MODEL_PATH else '未找到'}")
        self.log('-----------------------------')
        self.log(tr['Main']['StartProcessFrame'])
        self._delete_frame_cache()
        os.makedirs(self.frame_output_dir, exist_ok=True)
        os.makedirs(self.subtitle_output_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        options = {
            'REC_CHAR_TYPE': self.config.language.value,
            'DROP_SCORE': self.config.dropScore.value / 100.0,
            'SUB_AREA_DEVIATION_RATE': self.config.subtitleAreaDeviationRate.value / 100.0,
            'DEBUG_OCR_LOSS': self.config.debugOcrLoss.value,
            'HARDWARD_ACCELERATOR': None,
            'MODE': self.config.mode.value,
        }
        from types import SimpleNamespace
        options_ns = SimpleNamespace(**options)

        # 分段引擎（框选区域时的默认方式）：逐帧扫描 + 变化切段 + 每段一次 OCR。
        # 相比"按固定间隔抽样送帧"，它不会漏掉极短字幕，且起止时间精确到帧。
        if self.sub_area is not None and os.getenv('ZIMU_USE_VSF', '0') != '1' \
                and os.getenv('ZIMU_ENGINE', 'segment').lower() == 'segment':
            self._run_segment_engine(options_ns, start_time)
            return

        self.subtitle_ocr_task_queue, progress_queue, self.subtitle_ocr_thread, ocr_error = start_subtitle_ocr(
            self.video_path, self.raw_subtitle_path, self._ocr_sub_area(), options_ns, self.cancel_event)
        threading.Thread(target=self._monitor_ocr_progress, args=(progress_queue,), daemon=True).start()

        if self.cancel_event.is_set():
            raise RuntimeError('任务已取消')

        if self.sub_area is not None:
            # 默认用自研的区域内变化检测：VSF(debug 版) 会在中途断言崩溃，导致只识别前半段。
            # 需要的话设环境变量 ZIMU_USE_VSF=1 可以切回 VideoSubFinder。
            if os.getenv('ZIMU_USE_VSF', '0') == '1':
                self.extract_frame_by_vsf()
            else:
                self.extract_frame_by_region()
        else:
            self.extract_frame_by_fps()

        # 添加 OCR 结束标志
        self.subtitle_ocr_task_queue.put((self.frame_count, -1, None, None, None, None))
        if self.subtitle_ocr_thread:
            self.subtitle_ocr_thread.join(timeout=86400)

        if self.cancel_event.is_set():
            raise RuntimeError('任务已取消')
        if ocr_error.get('error'):
            raise RuntimeError(f'OCR 识别失败：{ocr_error["error"]}')

        self.log(tr['Main']['FinishProcessFrame'])
        self.log(tr['Main']['FinishFindSub'])

        if self.config.filterWatermark.value:
            self.log(tr['Main']['StartDetectWaterMark'])
            self.filter_watermark(auto=True)
            self.log(tr['Main']['FinishWaterMarkFilter'])

        if self.sub_area is None and self.config.filterSceneText.value:
            self.log(tr['Main']['StartDeleteNonSub'])
            self.filter_scene_text(auto=True)
            self.log(tr['Main']['FinishDeleteNoSubArea'])

        self.update_progress(post=20)
        self.log(tr['Main']['StartGenerateSub'])
        if self.use_vsf:
            self.generate_subtitle_file_vsf()
        else:
            self.generate_subtitle_file()

        self.update_progress(post=90)

        if self.config.wordSegmentation.value:
            self.log(tr['Main']['StartReformat'])
            reformat.execute(self.subtitle_output_path, self.config.language.value)
            self.log(tr['Main']['FinishReformat'])

        self.log(tr['Main']['FinishGenerateSub'], f"{round(time.time() - start_time, 2)}s")
        self.log('-----------------------------')
        self.update_progress(ocr=100, frame_extract=100, post=100)
        self.isFinished = True
        self._empty_cache()

        if self.config.generateTxt.value:
            self.srt2txt(self.subtitle_output_path)

    # ---------------- 分段引擎（逐帧扫描） ----------------

    def _scan_subtitle_spans(self, box):
        """逐帧扫描整段视频，用画面差分切出「可能有字幕」的时间段。

        返回 (spans, total_frames, threshold)，spans 是 [(start_frame, end_frame)]（1 基，含端点）。
        每一帧都会看，所以极短的字幕也不会被跳过。
        """
        x1, y1, x2, y2 = box
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError('无法读取视频')
        diffs = []
        prev = None
        idx = 0
        total_hint = int(self.frame_count) or 1
        try:
            while True:
                if self.cancel_event.is_set():
                    raise RuntimeError('任务已取消')
                ret, frame = cap.read()
                if not ret:
                    break
                idx += 1
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
                    crop = frame
                small = cv2.resize(crop, (256, 96), interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                # 用「文字掩膜」而不是灰度原图做差分：
                # 灰度差分受背景亮度整体变化影响大（噪声 P50 1.13 / 变化 P99 40.1）；
                # 二值化后只比"结构"，同样的开销下分离度更高（1.05 / 53.6）。
                _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                if prev is None:
                    diffs.append(0.0)
                else:
                    changed = cv2.countNonZero(cv2.bitwise_xor(mask, prev))
                    diffs.append(changed / float(mask.size) * 100.0)
                prev = mask.copy()
                if idx % 20 == 0:
                    self.update_progress(frame_extract=min(idx / total_hint, 1.0) * 45)
        finally:
            cap.release()
        if idx == 0:
            raise RuntimeError('读取视频帧失败')

        # 自适应阈值（单位：变化像素占区域面积的百分比）
        # 实测该视频噪声 P50≈1%、换句处 P90≈20%，取 8% 作下限足够区分
        arr = np.asarray(diffs[1:] or [0.0], dtype=np.float32)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med))) or 0.5
        thr = max(med + 6.0 * mad, 8.0)

        min_gap = max(int(round((self.fps or 25) / 10.0)), 2)   # 每段至少 0.1 秒
        bounds = [0]
        for i, d in enumerate(diffs):
            if d > thr and (i - bounds[-1]) >= min_gap:
                bounds.append(i)
        bounds.append(idx)
        spans = []
        for k in range(len(bounds) - 1):
            start = bounds[k] + 1
            end = bounds[k + 1]
            if end - start + 1 >= 2:
                spans.append((start, end))

        # 安全网：变化检测再漏，也不会让一个字幕段无限长。
        # 超过 max_span 的段强制切片，每片单独 OCR；文字相同的片会在后面合并回一条。
        # 默认 0.8 秒——任何显示超过 0.8 秒的字幕都至少被识别一次；可用 ZIMU_MAX_SPAN_MS 调整。
        try:
            span_ms = int(os.getenv('ZIMU_MAX_SPAN_MS', '800'))
        except ValueError:
            span_ms = 800
        max_span = max(int(round((self.fps or 25) * max(span_ms, 200) / 1000.0)), 6)
        capped = []
        for a, b in spans:
            cur = a
            while b - cur + 1 > max_span:
                capped.append((cur, cur + max_span - 1))
                cur += max_span
            capped.append((cur, b))
        return capped, idx, thr

    def _run_segment_engine(self, options_ns, start_time):
        """框选区域时的主流程：逐帧扫描切段 → 每段中间帧 OCR → 按帧号写 SRT

        优点：
          · 每一帧都参与判断，不会因为"抽样"漏掉短字幕
          · 段落起止由画面变化点决定，时间精确到帧（1/fps 秒）
          · 每个字幕段只 OCR 一次，整体比逐帧 OCR 快一个数量级
        """
        box = self._region_box()
        if box is None:
            box = (0, int(self.frame_height * 0.55), self.frame_width, self.frame_height)
        x1, y1, x2, y2 = box

        self.log('  逐帧扫描全片，按字幕变化切分时间段…')
        spans, scanned, thr = self._scan_subtitle_spans(box)
        self.log(f'  扫描 {scanned} 帧，切出 {len(spans)} 个字幕段（变化阈值 {thr:.1f}）')
        self.update_progress(frame_extract=50)
        if not spans:
            self.log('  未检测到字幕变化，生成的 SRT 为空')

        # OCR：每个段取中间帧（最稳定的一帧）；过长的段多点取样，防止把两句并成一条
        recogniser = OcrRecogniser()
        recogniser.language = options_ns.REC_CHAR_TYPE
        recogniser.mode = options_ns.MODE

        def read_frame(cap_, frame_no):
            cap_.set(cv2.CAP_PROP_POS_FRAMES, max(frame_no - 1, 0))
            ok, img = cap_.read()
            if not ok:
                return None
            piece = img[y1:y2, x1:x2]
            return piece if piece.size else img

        def ocr_text(cap_, frame_no):
            piece = read_frame(cap_, frame_no)
            if piece is None:
                return ''
            _dt, rec = recogniser.predict(piece)
            words = [t.strip() for t, p in rec if p >= options_ns.DROP_SCORE and t.strip()]
            return unicodedata.normalize('NFKC', ' '.join(words)).strip()

        cap = cv2.VideoCapture(self.video_path)
        raw_segments = []
        long_span = max(int((self.fps or 25) * 2.5), 12)   # 超过 2.5 秒的段做多点校验
        similarity = self.config.thresholdTextSimilarity.value / 100.0
        try:
            for k, (a, b) in enumerate(spans):
                if self.cancel_event.is_set():
                    raise RuntimeError('任务已取消')
                # 段内多点补采：中间帧可能正好落在换句/淡入瞬间而读空，逐点退让
                probes = []
                for p in ((a + b) // 2, a + (b - a) // 4, b - (b - a) // 4,
                          a + (b - a) // 10 + 1, b - (b - a) // 10):
                    p = min(max(p, a), b)
                    if p not in probes:
                        probes.append(p)
                got = None
                for p in probes:
                    text = ocr_text(cap, p)
                    if text:
                        got = (p, text)
                        break
                if got is None:
                    self.update_progress(ocr=50 + (k + 1) / max(len(spans), 1) * 50)
                    continue
                _p_mid, text_mid = got
                if (b - a + 1) > long_span:
                    # 长段：看首尾 1/4、3/4 处，文字不同就按中点拆开（防止两句并成一条）
                    t1 = ocr_text(cap, a + (b - a) // 4)
                    t3 = ocr_text(cap, b - (b - a) // 4)
                    if t1 and t3 and ratio(t1.replace(' ', ''), t3.replace(' ', '')) < similarity:
                        split = (a + b) // 2
                        raw_segments.append((a, split, t1))
                        raw_segments.append((split + 1, b, t3))
                        self.update_progress(ocr=50 + (k + 1) / max(len(spans), 1) * 50)
                        continue
                raw_segments.append((a, b, text_mid))
                self.update_progress(ocr=50 + (k + 1) / max(len(spans), 1) * 50)
        finally:
            cap.release()

        # 相邻同文字段合并（一次字幕被背景遮挡或抖动切成两段时还原成一段）
        similarity = self.config.thresholdTextSimilarity.value / 100.0
        merged = []
        for a, b, text in raw_segments:
            if merged:
                pa, pb, ptext = merged[-1]
                if ratio(ptext.replace(' ', ''), text.replace(' ', '')) >= similarity:
                    keep = ptext if len(ptext) >= len(text) else text
                    merged[-1] = (pa, max(pb, b), keep)
                    continue
            merged.append((a, b, text))

        with open(self.subtitle_output_path, mode='w', encoding='utf-8') as f:
            for i, (a, b, text) in enumerate(merged, start=1):
                start_tc = self._frame_to_timecode(a)
                end_tc = self._frame_to_timecode(b + 1)
                f.write(f'{i}\n{start_tc} --> {end_tc}\n{text}\n\n')

        self.log(f'  识别出 {len(merged)} 条字幕（每段只 OCR 一帧）')
        self.log(tr['Main']['FinishProcessFrame'])
        self.log(tr['Main']['FinishFindSub'])
        self.log(tr['Main']['SubLocation'].format(self.subtitle_output_path))
        if self.config.wordSegmentation.value and merged:
            self.log(tr['Main']['StartReformat'])
            reformat.execute(self.subtitle_output_path, self.config.language.value)
            self.log(tr['Main']['FinishReformat'])
        self.log(tr['Main']['FinishGenerateSub'], f'{round(time.time() - start_time, 2)}s')
        self.log('-----------------------------')
        self.update_progress(ocr=100, frame_extract=100, post=100)
        self.isFinished = True
        self._empty_cache()
        if self.config.generateTxt.value:
            self.srt2txt(self.subtitle_output_path)


    # ---------------- 首帧预览 ----------------

    def capture_preview_frame(self, at_ms: int = 0) -> str:
        """截取预览帧（画字幕区域框），返回图片路径"""
        os.makedirs(self.temp_output_dir, exist_ok=True)
        if self.video_cap is None or not self.video_cap.isOpened():
            self.video_cap = cv2.VideoCapture(self.video_path)
        self.video_cap.set(cv2.CAP_PROP_POS_MSEC, at_ms)
        ret, frame = self.video_cap.read()
        if not ret:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_cap.read()
        if not ret:
            raise RuntimeError('无法读取视频帧')
        sub_area = self.sub_area
        if sub_area is not None:
            cv2.rectangle(frame, (sub_area.xmin, sub_area.ymin), (sub_area.xmax, sub_area.ymax), (0, 255, 0), 2)
            cv2.putText(frame, 'Subtitle Area', (sub_area.xmin, max(sub_area.ymin - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        output_path = os.path.join(self.temp_output_dir, 'preview.jpg')
        imwrite_unicode(output_path, frame)
        return output_path

    # ---------------- 帧提取 ----------------

    def extract_frame_by_fps(self):
        frame_interval = int(self.fps // max(self.config.extractFrequency.value, 1))
        if frame_interval < 1:
            frame_interval = 1
        current_frame_no = 0
        total_frames = int(self.frame_count)
        while current_frame_no < total_frames:
            if self.cancel_event.is_set():
                return
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_no)
            ret, frame = self.video_cap.read()
            if not ret:
                break
            current_frame_no += 1
            self.subtitle_ocr_task_queue.put(
                (self.frame_count, current_frame_no, None, None, None, self.config.subtitleArea.value))
            self.update_progress(frame_extract=(current_frame_no / self.frame_count) * 100)
            current_frame_no = current_frame_no + frame_interval - 1
        self.video_cap.release()

    def extract_frame_by_det(self):
        current_frame_no = 0
        frame_lru_list = []
        frame_lru_list_max_size = 2
        ocr_args_list = []
        compare_ocr_result_cache = {}
        first_flag = True
        is_finding_start_frame_no = False
        is_finding_end_frame_no = False
        start_frame_no = 0
        start_end_frame_no = []
        start_frame = None
        if self.ocr is None:
            self.ocr = OcrRecogniser()
        while self.video_cap.isOpened():
            if self.cancel_event.is_set():
                break
            ret, frame = self.video_cap.read()
            if not ret:
                break
            current_frame_no += 1
            if self.sub_detector is None:
                self.sub_detector = SubtitleDetect(self.config.language.value, self.config.mode.value)
            dt_boxes, elapse = self.sub_detector.detect_subtitle(frame)
            has_subtitle = False
            sub_area = self.sub_area
            if sub_area is not None:
                coordinate_list = get_coordinates(dt_boxes.tolist() if hasattr(dt_boxes, 'tolist') else dt_boxes)
                if coordinate_list:
                    for coordinate in coordinate_list:
                        xmin, xmax, ymin, ymax = coordinate
                        if (sub_area.xmin <= xmin and xmax <= sub_area.xmax
                                and sub_area.ymin <= ymin and ymax <= sub_area.ymax):
                            has_subtitle = True
                            if first_flag:
                                is_finding_start_frame_no = True
                                first_flag = False
                            break
            else:
                has_subtitle = len(dt_boxes) > 0

            if has_subtitle:
                if is_finding_start_frame_no:
                    start_frame_no = current_frame_no
                    dt_box, rec_res = self.ocr.predict(frame)
                    area_text1 = ''.join(self.__get_area_text((dt_box, rec_res)))
                    if start_frame_no not in compare_ocr_result_cache.keys():
                        compare_ocr_result_cache[current_frame_no] = {'text': area_text1, 'dt_box': dt_box, 'rec_res': rec_res}
                        frame_lru_list.append((frame, current_frame_no))
                        ocr_args_list.append((self.frame_count, current_frame_no))
                        start_frame = frame
                    is_finding_start_frame_no = False
                    is_finding_end_frame_no = True
                if is_finding_end_frame_no and current_frame_no >= self.frame_count - 1:
                    is_finding_end_frame_no = False
                    is_finding_start_frame_no = False
                    end_frame_no = current_frame_no
                    frame_lru_list.append((frame, current_frame_no))
                    ocr_args_list.append((self.frame_count, current_frame_no))
                    start_end_frame_no.append((start_frame_no, end_frame_no))
                if is_finding_end_frame_no:
                    if not self._compare_ocr_result(compare_ocr_result_cache, None, start_frame_no, frame, current_frame_no):
                        is_finding_end_frame_no = False
                        is_finding_start_frame_no = True
                        end_frame_no = current_frame_no - 1
                        frame_lru_list.append((start_frame, end_frame_no))
                        ocr_args_list.append((self.frame_count, end_frame_no))
                        start_end_frame_no.append((start_frame_no, end_frame_no))
            else:
                if is_finding_end_frame_no:
                    end_frame_no = current_frame_no - 1
                    is_finding_end_frame_no = False
                    is_finding_start_frame_no = True
                    frame_lru_list.append((start_frame, end_frame_no))
                    ocr_args_list.append((self.frame_count, end_frame_no))
                    start_end_frame_no.append((start_frame_no, end_frame_no))

            while len(frame_lru_list) > frame_lru_list_max_size:
                frame_lru_list.pop(0)

            while len(ocr_args_list) > 1:
                total_frame_count, ocr_info_frame_no = ocr_args_list.pop(0)
                if current_frame_no in compare_ocr_result_cache:
                    predict_result = compare_ocr_result_cache[current_frame_no]
                    dt_box, rec_res = predict_result['dt_box'], predict_result['rec_res']
                else:
                    dt_box, rec_res = None, None
                self.subtitle_ocr_task_queue.put(
                    (total_frame_count, ocr_info_frame_no, dt_box, rec_res, None, self.config.subtitleArea.value))
                self.update_progress(frame_extract=(current_frame_no / self.frame_count) * 100)

        while len(ocr_args_list) > 0:
            total_frame_count, ocr_info_frame_no = ocr_args_list.pop(0)
            if current_frame_no in compare_ocr_result_cache:
                predict_result = compare_ocr_result_cache[current_frame_no]
                dt_box, rec_res = predict_result['dt_box'], predict_result['rec_res']
            else:
                dt_box, rec_res = None, None
            self.subtitle_ocr_task_queue.put(
                (total_frame_count, ocr_info_frame_no, dt_box, rec_res, None, self.config.subtitleArea.value))
        self.video_cap.release()

    def _region_box(self):
        """自定义字幕区域裁到帧范围内的像素框 (x1, y1, x2, y2)"""
        area = self.sub_area
        x1 = max(int(area.xmin), 0)
        y1 = max(int(area.ymin), 0)
        x2 = min(int(area.xmax), self.frame_width)
        y2 = min(int(area.ymax), self.frame_height)
        if x2 <= x1 or y2 <= y1:
            return None
        return (x1, y1, x2, y2)

    def _ocr_sub_area(self):
        """给 OCR 消费者用的过滤区域。

        区域取帧模式：生产者会先把帧裁到字幕框，OCR 出来的坐标是框内相对坐标，
        所以过滤区域也要换成框内坐标系（0,0,w,h），否则文字会被全部过滤掉。
        """
        if self.sub_area is None:
            return None
        if os.getenv('ZIMU_USE_VSF', '0') == '1':
            return self.sub_area
        box = self._region_box()
        if box is None:
            return None
        x1, y1, x2, y2 = box
        return SubtitleArea(ymin=0, ymax=y2 - y1, xmin=0, xmax=x2 - x1)

    def extract_frame_by_region(self):
        """纯 OpenCV 的「字幕区域内变化检测」——覆盖整段视频，不依赖 VideoSubFinder。

        为什么不用 VSF：随包附带的 VideoSubFinder 是 **debug 版**，内部断言一失败就
        STATUS_BREAKPOINT 直接终止（表现为任务很快"完成"，但只识别到视频前 1/3）。
        这里改成自己算：把字幕区域裁出来缩成小图做灰度差，
        变化超过阈值（字幕出现/消失/换句）或距上次推送超过 1.2 秒，就送去 OCR。
        好处：整段视频都扫，且只送少量帧，速度接近 VSF。
        """
        area = self.sub_area
        cap = self.video_cap
        total = int(self.frame_count) or 0
        if total <= 0:
            raise RuntimeError('读取视频帧数失败，无法提取字幕帧')
        # 每秒采样 5 帧用于判断变化（30fps -> 每 6 帧看一次）
        step = max(int(round((self.fps or 25) / 5.0)), 1)
        force_gap_ms = 1500          # 强制兜底间隔：保证长时间字幕也能覆盖
        diff_threshold = 8.0         # 灰度平均差阈值（越大送帧越少）
        prev_small = None
        last_sent_ms = -10 ** 9
        scanned = 0
        sent = 0
        x1 = max(int(area.xmin), 0)
        y1 = max(int(area.ymin), 0)
        x2 = min(int(area.xmax), self.frame_width)
        y2 = min(int(area.ymax), self.frame_height)

        idx = 0
        while idx < total:
            if self.cancel_event.is_set():
                return
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                break
            scanned += 1
            region = frame[y1:y2, x1:x2] if (x2 > x1 and y2 > y1) else frame
            if region.size == 0:
                region = frame
            small = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(small, (160, 60), interpolation=cv2.INTER_AREA)
            total_ms = int(idx / (self.fps or 25) * 1000)

            changed = True
            if prev_small is not None:
                diff = float(cv2.absdiff(small, prev_small).mean())
                changed = diff > diff_threshold

            if changed or (total_ms - last_sent_ms) >= force_gap_ms:
                # 关键：只传帧号、不传 total_ms。
                # 生产者按 CAP_PROP_POS_MSEC 定位在多支视频上都不准（帧会落在错误位置，
                # 表现为"只识别出前半段"）；按帧号 seek 才可靠。
                # 字幕时间戳由帧号换算，见 extract_subtitles 里的 data['i']。
                box = self._region_box()
                self.subtitle_ocr_task_queue.put(
                    (self.frame_count, idx + 1, None, None, None,
                     box if box is not None else self.config.subtitleArea.value))
                last_sent_ms = total_ms
                prev_small = small
                sent += 1

            idx += step
            self.update_progress(frame_extract=min(idx / total * 100, 100))
        cap.release()
        self.log(f'  区域取帧：扫描 {scanned} 帧（每 {step} 帧一次），送去识别 {sent} 帧')

    def extract_frame_by_vsf(self):
        self.use_vsf = True
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None

        def count_process():
            duration_ms = (self.frame_count / self.fps) * 1000
            last_total_ms = 0
            processed_image = set()
            rgb_images_path = os.path.join(self.temp_output_dir, 'RGBImages')
            time_pattern = re.compile(r'^\d+_\d+_\d+_\d+__')
            while (self.vsf_runner is not None and self.vsf_runner.running) and not self.isFinished:
                if self.cancel_event.is_set():
                    return
                time.sleep(0.2)
                if not os.path.exists(rgb_images_path):
                    continue
                try:
                    rgb_images = sorted(os.listdir(rgb_images_path))
                    for rgb_image in rgb_images:
                        if rgb_image in processed_image:
                            continue
                        if not time_pattern.match(rgb_image):
                            continue
                        processed_image.add(rgb_image)
                        h, m, s, ms = rgb_image.split('__')[0].split('_')
                        total_ms = int(ms) + int(s) * 1000 + int(m) * 60 * 1000 + int(h) * 60 * 60 * 1000
                        if total_ms > last_total_ms:
                            frame_no = int(total_ms / self.fps)
                            self.subtitle_ocr_task_queue.put(
                                (self.frame_count, frame_no, None, None, total_ms, self.config.subtitleArea.value))
                        last_total_ms = total_ms
                        if total_ms / duration_ms >= 1:
                            self.update_progress(frame_extract=100)
                            return
                        else:
                            self.update_progress(frame_extract=(total_ms / duration_ms) * 100)
                except FileNotFoundError:
                    return

        def vsf_output(out):
            duration_ms = (self.frame_count / self.fps) * 1000
            last_total_ms = 0
            for line in iter(out.readline, b''):
                if self.cancel_event.is_set():
                    return
                line = line.decode('utf-8', 'ignore')
                if line.startswith('Frame: '):
                    line = line.replace('\n', '').replace('Frame: ', '')
                    try:
                        h, m, s, ms = line.split('__')[0].split('_')
                        total_ms = int(ms) + int(s) * 1000 + int(m) * 60 * 1000 + int(h) * 60 * 60 * 1000
                    except Exception:
                        continue
                    if total_ms > last_total_ms:
                        frame_no = int(total_ms / self.fps)
                        self.subtitle_ocr_task_queue.put(
                            (self.frame_count, frame_no, None, None, total_ms, self.config.subtitleArea.value))
                    last_total_ms = total_ms
                    if duration_ms > 0 and total_ms / duration_ms >= 1:
                        self.update_progress(frame_extract=100)
                        return
                    else:
                        self.update_progress(frame_extract=(total_ms / duration_ms) * 100)
            out.close()

        os.makedirs(self.temp_output_dir, exist_ok=True)
        runner = VsfRunner(self.config)
        if not runner.exists:
            raise RuntimeError(f'未找到 VideoSubFinder 可执行文件：{runner.path_vsf}')
        self.vsf_runner = runner
        try:
            proc = runner.launch(self.video_path, self.temp_output_dir, self.vsf_subtitle,
                                 top=1 - self.sub_area.ymin / self.frame_height,
                                 bottom=1 - self.sub_area.ymax / self.frame_height,
                                 left=self.sub_area.xmin / self.frame_width,
                                 right=self.sub_area.xmax / self.frame_width)
            self.log(tr['Main']['RunVSF'])
            if runner.system == 'Windows':
                threading.Thread(target=count_process, daemon=True).start()
            elif proc is not None and proc.stderr is not None:
                threading.Thread(target=vsf_output, args=(proc.stderr,), daemon=True).start()
            runner.wait()
        finally:
            self.vsf_running = False
            runner.kill()

    # ---------------- 过滤 ----------------

    def filter_watermark(self, auto: bool = False):
        watermark_areas = self._detect_watermark_area()
        for watermark_area in watermark_areas:
            ymin = min(watermark_area[0][2], watermark_area[0][3])
            ymax = max(watermark_area[0][3], watermark_area[0][2])
            xmin = min(watermark_area[0][0], watermark_area[0][1])
            xmax = max(watermark_area[0][1], watermark_area[0][0])
            with open(self.raw_subtitle_path, mode='r+', encoding='utf-8') as f:
                content = f.readlines()
                f.seek(0)
                for i in content:
                    if i.find(str(watermark_area[0])) == -1:
                        f.write(i)
                f.truncate()
            self.log(tr['Main']['FinishDelete'], f'({xmin},{ymin})-({xmax},{ymax})')
        self.log(tr['Main']['FinishWaterMarkFilter'])

    def filter_scene_text(self, auto: bool = False):
        subtitle_area = self._detect_subtitle_area()[0][0]
        if not os.path.exists(self.raw_subtitle_path):
            return
        ymin = abs(subtitle_area[0] - self.config.subtitleAreaDeviationPixel.value)
        ymax = subtitle_area[1] + self.config.subtitleAreaDeviationPixel.value
        if ymin > ymax:
            ymin, ymax = ymax, ymin
        with open(self.raw_subtitle_path, mode='r+', encoding='utf-8') as f:
            content = f.readlines()
            f.seek(0)
            for i in content:
                try:
                    pos = i.split('\t')[1].split('(')[1].split(')')[0].split(', ')
                    i_ymin, i_ymax = int(pos[2]), int(pos[3])
                    if ymin <= i_ymin and i_ymax <= ymax:
                        f.write(i)
                except Exception:
                    continue
            f.truncate()
        self.log(tr['Main']['FinishDeleteNoSubArea'], f'y: {ymin} ~ {ymax}')

    # ---------------- 字幕文件生成 ----------------

    def generate_subtitle_file(self):
        if self.use_vsf:
            return
        subtitle_content = self._remove_duplicate_subtitle()
        with open(self.subtitle_output_path, mode='w', encoding='utf-8') as f:
            for index, content in enumerate(subtitle_content):
                line_code = index + 1
                frame_start = self._frame_to_timecode(int(content[0]))
                if abs(int(content[1]) - int(content[0])) < self.fps:
                    frame_end = self._frame_to_timecode(int(int(content[0]) + self.fps))
                else:
                    frame_end = self._frame_to_timecode(int(content[1]))
                f.write(f"{line_code}\n{frame_start} --> {frame_end}\n{content[2]}\n")
        self.log(tr['Main']['SubLocation'].format(self.subtitle_output_path))

    def generate_subtitle_file_vsf(self):
        if not os.path.exists(self.vsf_subtitle):
            self.log('VSF 未生成字幕文件，回退到常规方式')
            self.generate_subtitle_file()
            return
        subs = pysrt.open(self.vsf_subtitle)
        sub_no_map = {}
        for sub in subs:
            sub.start.no = self._timestamp_to_frameno(sub.start.ordinal)
            sub_no_map[sub.start.no] = sub

        subtitle_content = self._remove_duplicate_subtitle()
        subtitle_content_start_map = {int(a[0]): a for a in subtitle_content}
        final_subtitles = []
        for sub in subs:
            found = sub.start.no in subtitle_content_start_map
            if found:
                subtitle_content_line = subtitle_content_start_map[sub.start.no]
                sub.text = subtitle_content_line[2]
                end_no = int(subtitle_content_line[1])
                sub.end = sub_no_map[end_no].end if end_no in sub_no_map else sub.end
                sub.index = len(final_subtitles) + 1
                final_subtitles.append(sub)
            if not found and not self.config.deleteEmptyTimeStamp.value:
                sub.text = ''
                sub.index = len(final_subtitles) + 1
                final_subtitles.append(sub)
                continue

        pysrt.SubRipFile(final_subtitles).save(self.subtitle_output_path, encoding='utf-8')
        self.log(tr['Main']['SubLocation'].format(self.subtitle_output_path))

    # ---------------- 区域检测 ----------------

    def _detect_watermark_area(self):
        if not os.path.exists(self.raw_subtitle_path):
            return []
        with open(self.raw_subtitle_path, mode='r', encoding='utf-8') as f:
            lines = f.readlines()
        parsed = []
        for line in lines:
            parts = line.split('\t')
            if len(parts) < 3:
                continue
            frame_no = parts[0]
            text_position = parts[1].split('(')[1].split(')')[0].split(', ')
            content = parts[2]
            coordinate = (int(text_position[0]), int(text_position[1]),
                          int(text_position[2]), int(text_position[3]))
            parsed.append((frame_no, coordinate, content))

        frame_no_list = [p[0] for p in parsed]
        coordinates_list = [p[1] for p in parsed]
        content_list = [p[2] for p in parsed]
        coordinates_list = self._unite_coordinates(coordinates_list)

        with open(self.raw_subtitle_path, mode='w', encoding='utf-8') as f:
            for frame_no, coordinate, content in zip(frame_no_list, coordinates_list, content_list):
                f.write(f'{frame_no}\t{coordinate}\t{content}')

        count = Counter(coordinates_list).most_common()
        num = min(self.config.waterarkAreaNum.value, len(count))
        return count[:num]

    def _detect_subtitle_area(self):
        if not os.path.exists(self.raw_subtitle_path):
            return [(0, (0, 0))]
        with open(self.raw_subtitle_path, mode='r', encoding='utf-8') as f:
            lines = f.readlines()
        y_coordinates_list = []
        for line in lines:
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            text_position = parts[1].split('(')[1].split(')')[0].split(', ')
            y_coordinates_list.append((int(text_position[2]), int(text_position[3])))
        if not y_coordinates_list:
            return [(0, (0, 0))]
        return Counter(y_coordinates_list).most_common(1)

    # ---------------- 时间工具 ----------------

    def _frame_to_timecode(self, frame_no):
        total_ms = frame_no / self.fps * 1000
        total_ms_int = int(total_ms)
        milliseconds = total_ms_int % 1000
        total_seconds = total_ms_int // 1000
        seconds = total_seconds % 60
        minutes = (total_seconds // 60) % 60
        hours = total_seconds // 3600
        return '%02d:%02d:%02d,%03d' % (hours, minutes, seconds, milliseconds)

    def _timestamp_to_frameno(self, time_ms):
        return int(time_ms / self.fps)

    def _frameno_to_milliseconds(self, frame_no):
        return float(int(frame_no / self.fps * 1000))

    # ---------------- 去重（核心） ----------------

    def _remove_duplicate_subtitle(self):
        self._concat_content_with_same_frameno()
        if not os.path.exists(self.raw_subtitle_path):
            return []
        with open(self.raw_subtitle_path, mode='r', encoding='utf-8') as r:
            lines = r.readlines()
        RawInfo = namedtuple('RawInfo', 'no content')
        content_list = []
        for line in lines:
            parts = line.split('\t')
            if len(parts) < 3:
                continue
            content_list.append(RawInfo(parts[0], parts[2]))

        unique_subtitle_list = []
        idx_i = 0
        content_list_len = len(content_list)
        while idx_i < content_list_len:
            if self.cancel_event.is_set():
                return unique_subtitle_list
            i = content_list[idx_i]
            start_frame = i.no
            idx_j = idx_i
            while idx_j < content_list_len:
                if idx_j + 1 == content_list_len or \
                        ratio(i.content.replace(' ', ''), content_list[idx_j + 1].content.replace(' ', '')) < (
                                self.config.thresholdTextSimilarity.value / 100.0):
                    end_frame = content_list[idx_j].no
                    if not self.use_vsf:
                        if end_frame == start_frame and idx_j + 1 < content_list_len:
                            end_frame = content_list[idx_j + 1][0]
                    similar_list = content_list[idx_i:idx_j + 1]
                    similar_content_strip_list = [item.content.replace(' ', '') for item in similar_list]
                    index, _ = max(enumerate(similar_content_strip_list), key=lambda x: len(x[1]))
                    unique_subtitle_list.append((start_frame, end_frame, similar_list[index].content))
                    idx_i = idx_j + 1
                    break
                else:
                    idx_j += 1
                    continue
        return unique_subtitle_list

    def _concat_content_with_same_frameno(self):
        if not os.path.exists(self.raw_subtitle_path):
            return
        with open(self.raw_subtitle_path, mode='r', encoding='utf-8') as r:
            lines = r.readlines()

        grouped = OrderedDict()
        for line in lines:
            parts = line.split('\t', 2)
            if len(parts) < 3:
                continue
            frame_no, coordinate, content = parts
            if frame_no not in grouped:
                grouped[frame_no] = (coordinate, [])
            grouped[frame_no][1].append(content)

        with open(self.raw_subtitle_path, mode='w', encoding='utf-8') as f:
            for frame_no, (coordinate, contents) in grouped.items():
                merged = ' '.join(contents).replace('\n', ' ')
                if not merged.endswith('\n'):
                    merged += '\n'
                merged = unicodedata.normalize('NFKC', merged)
                f.write(f'{frame_no}\t{coordinate}\t{merged}')

    def _unite_coordinates(self, coordinates_list):
        if not coordinates_list:
            return coordinates_list
        n = len(coordinates_list)
        indexed = sorted(enumerate(coordinates_list), key=lambda x: x[1][0])
        parent = list(range(n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                if ri > rj:
                    ri, rj = rj, ri
                parent[rj] = ri

        left = 0
        for right in range(n):
            while left < right and indexed[right][1][0] - indexed[left][1][0] >= self.config.tolerantPixelX.value:
                left += 1
            for k in range(left, right):
                if self.__is_coordinate_similar(indexed[k][1], indexed[right][1]):
                    union(indexed[k][0], indexed[right][0])
        result = list(coordinates_list)
        for i in range(n):
            result[i] = coordinates_list[find(i)]
        return result

    def __is_coordinate_similar(self, coordinate1, coordinate2):
        return (abs(coordinate1[0] - coordinate2[0]) < self.config.tolerantPixelX.value and
                abs(coordinate1[1] - coordinate2[1]) < self.config.tolerantPixelX.value and
                abs(coordinate1[2] - coordinate2[2]) < self.config.tolerantPixelY.value and
                abs(coordinate1[3] - coordinate2[3]) < self.config.tolerantPixelY.value)

    def _compute_image_similarity(self, image1, image2):
        image1 = self.__get_thum(image1)
        image2 = self.__get_thum(image2)
        images = [image1, image2]
        vectors = []
        norms = []
        for image in images:
            vector = []
            for pixel_tuple in image.getdata():
                vector.append(average(pixel_tuple))
            vectors.append(vector)
            norms.append(linalg.norm(vector, 2))
        a, b = vectors
        a_norm, b_norm = norms
        res = dot(a / a_norm, b / b_norm)
        return res

    def __get_area_text(self, ocr_result):
        box, text = ocr_result
        coordinates = get_coordinates(box)
        area_text = []
        for content, coordinate in zip(text, coordinates):
            sub_area = self.sub_area
            if sub_area is not None:
                xmin, xmax, ymin, ymax = coordinate[0], coordinate[1], coordinate[2], coordinate[3]
                if sub_area.xmin <= xmin and xmax <= sub_area.xmax and sub_area.ymin <= ymin and ymax <= sub_area.ymax:
                    area_text.append(content[0])
        return area_text

    def _compare_ocr_result(self, result_cache, img1, img1_no, img2, img2_no):
        if img1_no in result_cache:
            area_text1 = result_cache[img1_no]['text']
        else:
            if self.ocr is None:
                self.ocr = OcrRecogniser()
            dt_box, rec_res = self.ocr.predict(img1)
            area_text1 = ''.join(self.__get_area_text((dt_box, rec_res)))
            result_cache[img1_no] = {'text': area_text1, 'dt_box': dt_box, 'rec_res': rec_res}

        if img2_no in result_cache:
            area_text2 = result_cache[img2_no]['text']
        else:
            if self.ocr is None:
                self.ocr = OcrRecogniser()
            dt_box, rec_res = self.ocr.predict(img2)
            area_text2 = ''.join(self.__get_area_text((dt_box, rec_res)))
            result_cache[img2_no] = {'text': area_text2, 'dt_box': dt_box, 'rec_res': rec_res}

        delete_no_list = []
        for no in result_cache:
            if no < min(img1_no, img2_no) - 10:
                delete_no_list.append(no)
        for no in delete_no_list:
            del result_cache[no]
        return ratio(area_text1, area_text2) > self.config.thresholdTextSimilarity.value / 100.0

    @staticmethod
    def __get_thum(image, size=(64, 64), greyscale=False):
        image = image.resize(size, Image.LANCZOS)
        if greyscale:
            image = image.convert('L')
        return image

    # ---------------- 缓存 ----------------

    def _delete_frame_cache(self):
        if os.path.exists(self.temp_output_dir):
            shutil.rmtree(self.temp_output_dir, True)

    def _empty_cache(self):
        if not self.config.debugNoDeleteCache.value:
            if os.path.exists(self.temp_output_dir):
                shutil.rmtree(self.temp_output_dir, True)

    # ---------------- 进度与日志 ----------------

    def update_progress(self, ocr=None, frame_extract=None, post=None):
        if ocr is not None:
            self.progress_ocr = max(0, min(100, ocr))
        if frame_extract is not None:
            self.progress_frame_extract = max(0, min(100, frame_extract))
        if post is not None:
            self.progress_post = max(0, min(100, post))
        if self.on_progress:
            try:
                self.on_progress(self.progress_ocr, self.progress_frame_extract, self.progress_post, self.isFinished)
            except Exception:
                pass

    def _monitor_ocr_progress(self, progress_queue):
        total_tasks = None
        while True:
            try:
                value = progress_queue.get(block=True, timeout=0.5)
            except Exception:
                if self.cancel_event.is_set() or self.isFinished:
                    return
                continue
            if isinstance(value, tuple) and len(value) == 2 and value[0] == -2:
                total_tasks = value[1]
                self.log(tr['Main']['StartFindSub'])
                continue
            if value == -1 or (isinstance(value, tuple) and len(value) == 2 and value[0] == -1):
                self.update_progress(ocr=100)
                return
            if isinstance(value, tuple) and len(value) == 2:
                _, processed_count = value
                if total_tasks and total_tasks > 0:
                    ocr_pct = min(99, processed_count / total_tasks * 100)
                else:
                    ocr_pct = min(99, processed_count)
                self.update_progress(ocr=ocr_pct)

    def log(self, *args):
        msg = ' '.join(str(a) for a in args)
        print(f'[extract] {msg}')
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass

    # ---------------- 其他 ----------------

    def srt2txt(self, srt_file):
        if not os.path.exists(srt_file):
            return
        subs = pysrt.open(srt_file, encoding='utf-8')
        with open(self.txt_output_path, 'w', encoding='utf-8') as f:
            for sub in subs:
                f.write(f'{sub.text}\n')
        self.log(tr['Main']['SubLocation'].format(self.txt_output_path))

    vsf_running = False
