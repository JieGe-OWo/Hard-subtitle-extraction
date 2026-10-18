import subprocess


class VSFProcess:
    """管理 VideoSubFinder 子进程，支持取消"""

    def __init__(self):
        self.proc = None

    def start(self, cmd):
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     bufsize=1, shell=False)
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

    def close_pipes(self):
        if not self.proc:
            return
        for pipe in (self.proc.stdout, self.proc.stderr):
            try:
                if pipe:
                    pipe.close()
            except Exception:
                pass

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None
