import multiprocessing
import os
import platform
import subprocess

from app.config import SUBFINDER_DIR
from app.services.extraction.tr import tr


class VsfRunner:
    """VideoSubFinder 调用封装（CPU 版，不使用 CUDA）"""

    def __init__(self, config):
        self.config = config
        self.system = platform.system()
        self.path_vsf = self._resolve_path()
        self.proc = None

    def _resolve_path(self):
        base = str(SUBFINDER_DIR)
        if self.system == 'Windows':
            return os.path.join(base, 'windows', 'VideoSubFinderWXW.exe')
        if self.system == 'Darwin':
            return os.path.join(base, 'macos', 'VideoSubFinderCli')
        return os.path.join(base, 'linux', 'VideoSubFinderCli.run')

    @property
    def exists(self):
        return os.path.exists(self.path_vsf)

    def _cpu_count(self):
        cpu_count = max(multiprocessing.cpu_count() - 2, 1)
        if self.config.videoSubFinderCpuCores.value > 0:
            cpu_count = self.config.videoSubFinderCpuCores.value
        return cpu_count

    def launch(self, video_path, output_dir, vsf_subtitle, top, bottom, left, right):
        decoder = str(self.config.videoSubFinderDecoder.value).lower()
        cpu_count = self._cpu_count()
        common = (f'-c -r -i "{video_path}" -o "{output_dir}" -ces "{vsf_subtitle}" '
                  f'-te {top} -be {bottom} -le {left} -re {right} -nthr {cpu_count} '
                  f'--open_video_{decoder} ')
        # 工作目录设成 VSF 自己的目录：它会相对 CWD 找 settings，
        # 同时避免 CWD 落在含中文的软件目录里（C++ 组件的 ANSI 路径问题）
        workdir = os.path.dirname(self.path_vsf) or None
        if self.system == 'Windows':
            cmd = f'"{self.path_vsf}" ' + common + f'-nocrthr {cpu_count} '
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         bufsize=1, shell=False, cwd=workdir)
        else:
            if os.path.exists(self.path_vsf):
                os.chmod(self.path_vsf, 0o775)
            cmd = f'"{self.path_vsf}" ' + common + '-dsi '
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         bufsize=1, shell=True, start_new_session=True, cwd=workdir)
        return self.proc

    def wait(self, timeout=None):
        if self.proc:
            self.proc.wait(timeout=timeout)

    def kill(self):
        p = self.proc
        if not p:
            return
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass
        for pipe in (p.stdout, p.stderr):
            try:
                if pipe:
                    pipe.close()
            except Exception:
                pass

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None
