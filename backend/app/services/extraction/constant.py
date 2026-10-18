from enum import Enum


# 默认字幕出现的大致区域
class SubtitleArea(Enum):
    LOWER_PART = 0
    UPPER_PART = 1
    UNKNOWN = 2


class VideoSubFinderDecoder(Enum):
    OPENCV = "OpenCV"
    FFMPEG = "FFmpeg"


BGR_COLOR_GREEN = (0, 0xff, 0)
BGR_COLOR_BLUE = (0xff, 0, 0)
BGR_COLOR_RED = (0, 0, 0xff)
BGR_COLOR_WHITE = (0xff, 0xff, 0xff)
