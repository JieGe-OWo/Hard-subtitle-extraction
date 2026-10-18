"""OpenCV 图片读写的 Unicode 安全封装。

Windows 上 cv2.imwrite / cv2.imread 走的是 ANSI 文件接口，路径里一旦出现中文
（例如软件装在「D:\\软件\\杰哥硬字幕提取\\」）就会静默失败。
这里改成「内存编码 + numpy 落盘」，与路径字符集无关。

用法与 cv2 保持一致：
    imwrite_unicode(path, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    img = imread_unicode(path)
"""
import os

import cv2
import numpy as np


def imwrite_unicode(path: str, img, params=None) -> bool:
    """把图像写到任意（含中文）路径，成功返回 True"""
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
        ext = '.png'
    try:
        ok, buf = cv2.imencode(ext, img, params or [])
        if not ok:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False


def imread_unicode(path: str, flags=cv2.IMREAD_COLOR):
    """从任意（含中文）路径读图，失败返回 None"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except Exception:
        return None
    if data.size == 0:
        return None
    try:
        return cv2.imdecode(data, flags)
    except Exception:
        return None
