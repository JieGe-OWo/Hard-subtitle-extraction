import os
import re
import queue
from threading import Thread

import cv2
from PIL import ImageFont, ImageDraw
from tqdm import tqdm

from app.services.extraction.ocr import OcrRecogniser, get_coordinates
from app.services.extraction.constant import SubtitleArea, BGR_COLOR_GREEN, BGR_COLOR_RED, BGR_COLOR_BLUE
from app.services.extraction.tr import tr
from app.services.unicode_io import imwrite_unicode


def extract_subtitles(data, text_recogniser, img, raw_subtitles,
                      sub_area, options, dt_box_arg, rec_res_arg, ocr_loss_debug_path):
    dt_box = dt_box_arg
    rec_res = rec_res_arg
    if dt_box is None or rec_res is None:
        dt_box, rec_res = text_recogniser.predict(img)
    coordinates = get_coordinates(dt_box)
    if options.REC_CHAR_TYPE == 'en':
        text_res = [(re.sub('[一-龿]', '', res[0]), res[1]) for res in rec_res]
    else:
        text_res = [(res[0], res[1]) for res in rec_res]
    line = ''
    loss_list = []
    for content, coordinate in zip(text_res, coordinates):
        text = content[0]
        prob = content[1]
        if sub_area is not None:
            selected = False
            overflow_area_rate = 0
            c_xmin, c_xmax, c_ymin, c_ymax = coordinate
            inter_xmin = max(sub_area.xmin, c_xmin)
            inter_ymin = max(sub_area.ymin, c_ymin)
            inter_xmax = min(sub_area.xmax, c_xmax)
            inter_ymax = min(sub_area.ymax, c_ymax)
            has_intersection = inter_xmin < inter_xmax and inter_ymin < inter_ymax
            drop_reason = ''
            if has_intersection:
                sub_area_w = sub_area.xmax - sub_area.xmin
                sub_area_h = sub_area.ymax - sub_area.ymin
                sub_area_size = sub_area_w * sub_area_h
                inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
                coord_area = (c_xmax - c_xmin) * (c_ymax - c_ymin)
                overflow_area_rate = ((sub_area_size + coord_area - inter_area) / sub_area_size) - 1
                not_overflow = overflow_area_rate <= options.SUB_AREA_DEVIATION_RATE
                confident = prob > options.DROP_SCORE
                if not_overflow and confident:
                    selected = True
                    line += f'{str(data["i"]).zfill(8)}\t{coordinate}\t{text}\n'
                    raw_subtitles.append(f'{str(data["i"]).zfill(8)}\t{coordinate}\t{text}\n')
                else:
                    if not not_overflow:
                        drop_reason = tr['Main']['OcrDropOutOfBoxRate'].format(
                            int(options.SUB_AREA_DEVIATION_RATE * 100), int(overflow_area_rate * 100))
                    elif not confident:
                        drop_reason = tr['Main']['OcrDropConfidentLow'].format(int(options.DROP_SCORE * 100))
            else:
                drop_reason = tr['Main']['OcrDropNoIntercetion']
            if drop_reason:
                tqdm.write(tr['Main']['OcrResultWithDropReason'].format(text, round(prob * 100, 1), drop_reason))
            else:
                tqdm.write(tr['Main']['OcrResult'].format(text, round(prob * 100, 1)))
            import numpy as np
            from types import SimpleNamespace
            loss_info = SimpleNamespace(text=text, prob=prob, overflow_area_rate=overflow_area_rate,
                                        coordinate=coordinate, selected=selected)
            loss_list.append(loss_info)
        else:
            raw_subtitles.append(f'{str(data["i"]).zfill(8)}\t{coordinate}\t{text}\n')
    dump_debug_info(options, line, img, loss_list, ocr_loss_debug_path, sub_area, data)


def dump_debug_info(options, line, img, loss_list, ocr_loss_debug_path, sub_area, data):
    loss = False
    if options.DEBUG_OCR_LOSS and options.REC_CHAR_TYPE in ('ch', 'japan ', 'korea', 'ch_tra'):
        loss = len(line) > 0 and re.search(r'[一-鿿㐀-䶿㄰-㆏가-힣]', line) is None
    if loss:
        if not os.path.exists(ocr_loss_debug_path):
            os.makedirs(ocr_loss_debug_path, mode=0o777, exist_ok=True)
        img = cv2.rectangle(img, (sub_area.xmin, sub_area.ymin), (sub_area.xmax, sub_area.ymax),
                            BGR_COLOR_BLUE, 2)
        for loss_info in loss_list:
            coordinate = loss_info.coordinate
            color = BGR_COLOR_GREEN if loss_info.selected else BGR_COLOR_RED
            text = f"[{loss_info.text}] prob:{loss_info.prob:.4f} or:{loss_info.overflow_area_rate:.2f}"
            img = paint_chinese_opencv(img, text, pos=(coordinate[0], coordinate[2] - 30), color=color)
            img = cv2.rectangle(img, (coordinate[0], coordinate[2]), (coordinate[1], coordinate[3]), color, 2)
        imwrite_unicode(os.path.join(os.path.abspath(ocr_loss_debug_path), f'{str(data["i"]).zfill(8)}.png'), img)


FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'NotoSansCJK-Bold.otf')
FONT = ImageFont.truetype(FONT_PATH, 20)


def paint_chinese_opencv(im, chinese, pos, color):
    import numpy as np
    img_pil = Image.fromarray(im)
    draw = ImageDraw.Draw(img_pil)
    draw.text(pos, chinese, font=FONT, fill=color)
    return np.array(img_pil)


def ocr_task_consumer(ocr_queue, raw_subtitle_path, sub_area, video_path, options, progress_queue,
                      cancel_event=None, error_info=None):
    data = {'i': 1}
    text_recogniser = OcrRecogniser()
    text_recogniser.hardware_accelerator = options.HARDWARD_ACCELERATOR
    text_recogniser.language = options.REC_CHAR_TYPE
    text_recogniser.mode = options.MODE
    ocr_loss_debug_path = os.path.join(os.path.abspath(os.path.splitext(video_path)[0]), 'loss')
    if os.path.exists(ocr_loss_debug_path):
        import shutil
        shutil.rmtree(ocr_loss_debug_path, True)

    raw_subtitles = []
    processed_count = 0
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                progress_queue.put(-1)
                return
            try:
                frame_no, frame, dt_box, rec_res = ocr_queue.get(block=True, timeout=0.5)
                if frame_no == -1:
                    total_tasks = frame if frame is not None else processed_count
                    progress_queue.put((-1, total_tasks))
                    return
                data['i'] = frame_no
                extract_subtitles(data, text_recogniser, frame, raw_subtitles, sub_area, options, dt_box,
                                  rec_res, ocr_loss_debug_path)
                processed_count += 1
                progress_queue.put((frame_no, processed_count))
            except queue.Empty:
                continue
            except Exception as e:
                print(f'[ocr] {e}')
                import traceback
                traceback.print_exc()
                if error_info is not None:
                    error_info['error'] = str(e)
                progress_queue.put(-1)
                break
    finally:
        with open(raw_subtitle_path, mode='w+', encoding='utf-8') as raw_subtitle_file:
            for line in raw_subtitles:
                raw_subtitle_file.write(line)


def ocr_task_producer(ocr_queue, task_queue, progress_queue, video_path, raw_subtitle_path,
                      cancel_event=None, consumer_state=None):
    cap = cv2.VideoCapture(video_path)
    tbar = None
    frame_count = 0
    while True:
        if cancel_event is not None and cancel_event.is_set():
            break
        if consumer_state is not None and consumer_state.get('thread') is not None \
                and not consumer_state['thread'].is_alive():
            print('[ocr] 消费者线程已退出，停止生产')
            break
        try:
            total_frame_count, current_frame_no, dt_box, rec_res, total_ms, default_subtitle_area = \
                task_queue.get(block=True, timeout=0.5)
            if tbar is None:
                tbar = tqdm(total=round(total_frame_count), position=1)
            if current_frame_no == -1:
                ocr_queue.put((-1, frame_count, None, None))
                progress_queue.put((-2, frame_count))
                tbar.update(tbar.total - tbar.n)
                break
            tbar.update(round(current_frame_no - tbar.n))
            if total_ms is not None:
                # 注意：cv2 里这个常量叫 CAP_PROP_POS_MSEC；
                # 写成 CAP_PROP_MSEC 会抛 AttributeError，生产者线程直接死掉，
                # 结束标记永远发不出去，消费者空转 → 任务卡死在 running
                cap.set(cv2.CAP_PROP_POS_MSEC, total_ms)
            else:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_no - 1)
            ret, frame = cap.read()
            if ret:
                frame_count += 1
                if default_subtitle_area is not None:
                    frame = frame_preprocess(default_subtitle_area, frame)
                while True:
                    try:
                        ocr_queue.put((current_frame_no, frame, dt_box, rec_res), block=True, timeout=0.5)
                        break
                    except queue.Full:
                        if cancel_event is not None and cancel_event.is_set():
                            return
                        if consumer_state is not None and consumer_state.get('thread') is not None \
                                and not consumer_state['thread'].is_alive():
                            return
                        continue
        except queue.Empty:
            continue
        except Exception as e:
            print(f'[ocr producer] {e}')
            break
    cap.release()


def subtitle_extract_handler(task_queue, progress_queue, video_path, raw_subtitle_path, sub_area, options,
                             cancel_event=None, error_info=None):
    if os.path.exists(raw_subtitle_path):
        os.remove(raw_subtitle_path)
    ocr_queue = queue.Queue(20)
    consumer_state = {}
    producer_thread = Thread(target=ocr_task_producer,
                             args=(ocr_queue, task_queue, progress_queue, video_path, raw_subtitle_path,
                                   cancel_event, consumer_state),
                             daemon=True)
    consumer_thread = Thread(target=ocr_task_consumer,
                             args=(ocr_queue, raw_subtitle_path, sub_area, video_path, options, progress_queue,
                                   cancel_event, error_info),
                             daemon=True)
    consumer_state['thread'] = consumer_thread
    producer_thread.start()
    consumer_thread.start()
    producer_thread.join()
    # 兜底：生产者若异常退出（例如读帧失败），结束标记没能送达，
    # 消费者会永远等下去。这里补发一个结束标记，保证任务一定能收尾。
    if consumer_thread.is_alive():
        try:
            ocr_queue.put((-1, None, None, None), block=True, timeout=2)
        except queue.Full:
            pass
    consumer_thread.join()


def start_subtitle_ocr(video_path, raw_subtitle_path, sub_area, options, cancel_event=None):
    """以线程方式启动 OCR 流水线：返回 (task_queue, progress_queue, thread, error_info)"""
    task_queue = queue.Queue()
    progress_queue = queue.Queue()
    error_info = {}
    t = Thread(target=subtitle_extract_handler,
               args=(task_queue, progress_queue, video_path, raw_subtitle_path, sub_area, options,
                     cancel_event, error_info),
               daemon=True)
    t.start()
    return task_queue, progress_queue, t, error_info


def frame_preprocess(subtitle_area, frame):
    # 自定义区域：生产者直接把帧裁到字幕框，OCR 只算这一小块（快 5~10 倍）
    if isinstance(subtitle_area, (tuple, list)) and len(subtitle_area) == 4:
        x1, y1, x2, y2 = (int(v) for v in subtitle_area)
        h, w = frame.shape[:2]
        x1, y1 = max(x1, 0), max(y1, 0)
        x2, y2 = min(x2, w), min(y2, h)
        if x2 > x1 and y2 > y1:
            return frame[y1:y2, x1:x2]
        return frame
    if subtitle_area == SubtitleArea.LOWER_PART:
        cropped = int(frame.shape[0] // 2)
        frame = frame[cropped:]
    elif subtitle_area == SubtitleArea.UPPER_PART:
        cropped = int(frame.shape[0] // 2)
        frame = frame[:cropped]
    return frame
