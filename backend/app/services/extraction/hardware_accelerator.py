class HardwareAccelerator:
    """CPU 部署版硬件加速器：不启用任何 GPU/ONNX 后端"""

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = HardwareAccelerator()
        return cls._instance

    def __init__(self):
        self.__enabled = False

    def set_enabled(self, enable):
        self.__enabled = False  # 固定 CPU

    def has_accelerator(self):
        return False

    def has_cuda(self):
        return False

    @property
    def accelerator_name(self):
        return 'CPU'

    @property
    def onnx_providers(self):
        return []
