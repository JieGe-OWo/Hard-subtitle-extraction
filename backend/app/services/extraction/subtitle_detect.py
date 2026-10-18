import os

try:
    from paddleocr import TextDetection
except ImportError:
    TextDetection = None

from app.config import BASE_DIR
from app.services.extraction.paddle_model_config import PaddleModelConfig


class SubtitleDetect:
    """文本检测器（用于精准模式下的字幕帧定位）"""

    def __init__(self, language: str = 'ch', mode: str = 'fast'):
        model_config = PaddleModelConfig(language, mode)
        kwargs = {'model_dir': model_config.DET_MODEL_PATH}
        if model_config.DET_MODEL_NAME:
            kwargs['model_name'] = model_config.DET_MODEL_NAME
        self.text_detector = TextDetection(**kwargs)

    def detect_subtitle(self, img):
        import numpy as np
        results = list(self.text_detector.predict(img))
        if not results:
            return np.array([]), 0
        res = results[0]
        dt_polys = res.get('dt_polys', None)
        if dt_polys is None:
            return np.array([]), 0
        return dt_polys, 0
