from dataclasses import dataclass
from typing import Union


@dataclass
class SubtitleArea:
    """字幕区域（像素坐标）"""

    ymin: Union[int, float]
    ymax: Union[int, float]
    xmin: Union[int, float]
    xmax: Union[int, float]

    def __init__(self, ymin, ymax, xmin, xmax, ab_section=None):
        self.ymin = int(ymin)
        self.ymax = int(ymax)
        self.xmin = int(xmin)
        self.xmax = int(xmax)
        self.ab_section = ab_section

    def normalized(self):
        if self.xmin > self.xmax:
            self.xmin, self.xmax = self.xmax, self.xmin
        if self.ymin > self.ymax:
            self.ymin, self.ymax = self.ymax, self.ymin

    def is_empty(self):
        return self.xmin == 0 and self.xmax == 0 and self.ymin == 0 and self.ymax == 0

    @property
    def width(self):
        return self.xmax - self.xmin

    @property
    def height(self):
        return self.ymax - self.ymin

    def to_dict(self):
        return {'ymin': self.ymin, 'ymax': self.ymax, 'xmin': self.xmin, 'xmax': self.xmax}
