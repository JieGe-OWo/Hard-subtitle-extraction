"""运行期路径解析：让 C++ 组件在「中文路径」下也能正常工作。

背景
----
Windows 上 Paddle Inference、VideoSubFinder 等 C++ 组件大量使用 ANSI 文件接口，
软件目录一旦含中文（例如解压到 `D:\\软件\\杰哥硬字幕提取`），就会出现：
    · 读不到 OCR 模型 -> json 解析空输入
    · 写不出图片 / 读不到视频
而纯 Python 部分（含 cv2.VideoCapture）是好的，所以只在个别环节炸，很难查。

策略
----
软件路径不是纯 ASCII 时，在纯英文目录（`C:\\Users\\Public\\JiegeZiMuRuntime\\<指纹>`）
下为 models / subfinder / data 建立**目录联接（junction）**指向真实目录：
    · 交给 C++ 组件的路径变成纯英文，编码问题彻底消失
    · 文件仍然实际落在软件目录内，整个文件夹拷走依旧可用（数据不丢）

如果文件系统不支持联接（FAT32/exFAT 的 U 盘等）：
    · models / subfinder：退化为复制一份到英文目录（一次性，首次启动稍慢）
    · data：继续用软件目录内的真实路径（纯 Python + 已修好的图片读写仍可工作）
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # 软件内的 backend 目录
MIRROR_NAMES = ('models', 'subfinder', 'data')


def is_ascii_path(path) -> bool:
    try:
        str(path).encode('ascii')
        return True
    except (UnicodeEncodeError, AttributeError):
        return False


def _fingerprint(path: Path) -> str:
    return hashlib.sha1(str(path).encode('utf-8')).hexdigest()[:10]


def _candidate_bases():
    """英文镜像的候选根目录，按可用性依次尝试（不同机器权限不一样）"""
    cands = []
    drive = BASE_DIR.drive or 'C:'
    cands.append(Path(f'{drive}\\JiegeZiMuRuntime'))
    for env in ('PUBLIC', 'PROGRAMDATA', 'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'TEMP', 'TMP'):
        val = os.environ.get(env)
        if val:
            cands.append(Path(val) / 'JiegeZiMuRuntime')
    seen, out = set(), []
    for c in cands:
        key = str(c).lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


_DIAG = []   # 自检信息，供 desktop.py --diag 与日志输出


def _pick_mirror_base():
    """返回第一个可用的英文镜像根目录；都没有则返回 None

    优先复用上一次启动已经建好的镜像（此时目录里已有 models/subfinder 联接），
    没有再尝试新建并做一次写测试。每个候选的结果都记进 _DIAG，便于排障。
    """
    fp = _fingerprint(BASE_DIR)
    for cand in _candidate_bases():
        if not is_ascii_path(cand):
            _DIAG.append(f'跳过（含非 ASCII）：{cand}')
            continue
        base = cand / fp
        if (base / 'models').exists() or (base / 'subfinder').exists():
            _DIAG.append(f'复用已有镜像：{base}')
            return base
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / '.write_test'
            probe.write_text('ok', encoding='ascii')
            probe.unlink()
            _DIAG.append(f'可写：{base}')
            return base
        except Exception as exc:
            _DIAG.append(f'不可写（{type(exc).__name__}）：{cand} -> {str(exc)[:70]}')
            continue
    return None


def _make_junction(link: Path, target: Path) -> bool:
    """建立目录联接（免管理员权限）。成功返回 True"""
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
            capture_output=True, text=True, timeout=60,
        )
        return proc.returncode == 0 and link.exists()
    except Exception:
        return False


def _copy_dir_with_marker(src: Path, dst: Path) -> bool:
    """复制目录，完成后写 .ready 标记，避免每次启动重复复制"""
    marker = dst / '.ready'
    if marker.exists():
        return True
    if not src.exists():
        return False
    try:
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        marker.write_text('ok', encoding='ascii')
        return True
    except Exception:
        return False


def _prepare_mirror(base: Path):
    """返回 {名字: 可用路径}，失败的名字回落到软件目录内的真实路径"""
    resolved = {}
    for name in MIRROR_NAMES:
        real = BASE_DIR / name
        link = base / name
        if name == 'data':
            real.mkdir(parents=True, exist_ok=True)
        if link.exists():
            resolved[name] = link
            continue
        if real.exists() and _make_junction(link, real):
            resolved[name] = link
            continue
        if name == 'data':
            # 数据目录必须和软件在一起，联接失败就继续用原路径
            resolved[name] = real
            continue
        if _copy_dir_with_marker(real, link):
            resolved[name] = link
        else:
            resolved[name] = real
    return resolved


def _resolve():
    if is_ascii_path(BASE_DIR):
        _DIAG.append('软件路径为纯 ASCII，无需镜像')
        return BASE_DIR, False, {n: BASE_DIR / n for n in MIRROR_NAMES}
    try:
        base = _pick_mirror_base()
        if base is not None:
            resolved = _prepare_mirror(base)
            for name, path in resolved.items():
                _DIAG.append(f'{name} -> {path}')
            return base, True, resolved
        _DIAG.append('所有候选英文目录都不可写，退回原始路径（提取可能失败）')
    except Exception as exc:  # 建不了英文镜像就退回真实路径
        _DIAG.append(f'镜像创建异常：{type(exc).__name__}: {str(exc)[:120]}')
    return BASE_DIR, False, {n: BASE_DIR / n for n in MIRROR_NAMES}


RUNTIME_ROOT, ASCII_MIRROR, _RESOLVED = _resolve()

MODELS_DIR = _RESOLVED['models']
SUBFINDER_DIR = _RESOLVED['subfinder']
DATA_DIR = _RESOLVED['data']


def summary() -> str:
    if not ASCII_MIRROR:
        return f'路径模式：原生（{BASE_DIR}）'
    return (f'路径模式：英文镜像（软件目录含中文）\n'
            f'  镜像根目录：{RUNTIME_ROOT}\n'
            f'  模型：{MODELS_DIR}\n'
            f'  组件：{SUBFINDER_DIR}\n'
            f'  数据：{DATA_DIR}')


def diagnostics():
    """自检信息：路径判断过程，出问题时给用户/我排查用"""
    return list(_DIAG)


if __name__ == '__main__':
    print(summary())
    for _line in diagnostics():
        print('  ' + _line)
