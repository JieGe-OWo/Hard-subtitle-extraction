"""预览帧抓取。

只依赖 OpenCV，刻意不引入提取引擎（PaddleOCR / VideoSubFinder），
否则上传请求会被几秒钟的模型加载拖住，表现为「上传后长时间没响应」。
"""
import os
import threading

import cv2

from app.services.unicode_io import imwrite_unicode


class VideoPreview:
    """按需抓取视频帧并写出 JPEG 预览图（线程安全，视频句柄懒加载）。"""

    def __init__(self, video_path: str):
        self.video_path = video_path
        self._cap = None
        self._lock = threading.Lock()

    def _capture(self):
        if self._cap is None or not self._cap.isOpened():
            self._cap = cv2.VideoCapture(self.video_path)
        return self._cap

    def close(self):
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def grab(self, at_ms: int = 0, output_path: str = None, sub_area: dict = None) -> str:
        """抓取 at_ms 处的帧并写为 JPEG，返回写出路径。"""
        if not output_path:
            raise RuntimeError('缺少预览输出路径')
        with self._lock:
            cap = self._capture()
            if not cap.isOpened():
                raise RuntimeError('无法打开视频，请检查文件格式是否受支持')

            cap.set(cv2.CAP_PROP_POS_MSEC, max(int(at_ms), 0))
            ok, frame = cap.read()
            if not ok:
                # 定位失败（例如超出时长）时回退到首帧
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            if not ok:
                raise RuntimeError('无法读取视频帧')

            if sub_area:
                try:
                    x1, y1 = int(sub_area['xmin']), int(sub_area['ymin'])
                    x2, y2 = int(sub_area['xmax']), int(sub_area['ymax'])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                except (KeyError, TypeError, ValueError):
                    pass

            parent = os.path.dirname(output_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            # 先写临时文件再原子替换，避免浏览器读到写了一半的图
            # 用 unicode 安全写法：软件目录常含中文，cv2.imwrite 在中文路径下会失败
            tmp_path = f'{output_path}.tmp.jpg'
            if not imwrite_unicode(tmp_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88]):
                raise RuntimeError('预览图写入失败')
            os.replace(tmp_path, output_path)
            return output_path
