class _V:
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f'Setting({self.value!r})'


class ExtractionConfig:
    """提取参数默认值，CPU 部署，硬件加速默认关闭"""

    def __init__(self, **overrides):
        defaults = dict(
            language='ch',
            mode='fast',
            generateTxt=True,
            recBatchNumber=6,
            maxBatchSize=10,
            subtitleArea=2,
            extractFrequency=3,
            tolerantPixelY=50,
            tolerantPixelX=100,
            subtitleAreaDeviationPixel=50,
            waterarkAreaNum=5,
            thresholdTextSimilarity=80,
            dropScore=75,
            subtitleAreaDeviationRate=0,
            debugOcrLoss=False,
            debugNoDeleteCache=False,
            deleteEmptyTimeStamp=True,
            wordSegmentation=True,
            hardwareAcceleration=False,
            videoSubFinderCpuCores=0,
            videoSubFinderDecoder='OpenCV',
            filterWatermark=False,
            filterSceneText=True,
        )
        for k, v in defaults.items():
            setattr(self, k, _V(overrides.get(k, v)))

    def as_dict(self):
        return {k: getattr(self, k).value for k in self.__dict__}
