"""把项目打包成 Windows 便携版：解压即用，目标机器无需安装 Python / MySQL。

产物目录结构（dist_portable/杰哥硬字幕提取/）：
    runtime/            便携 Python 3.12 运行时 + 全部第三方依赖
    backend/            app 源码 + models(V5 全量模型) + subfinder/windows + desktop.py
    frontend/dist/      前端构建产物（由后端托管）
    启动 杰哥硬字幕提取.bat
    调试启动.bat
    使用说明.txt

用法：
    backend\\venv\\Scripts\\python.exe build_portable.py
    backend\\venv\\Scripts\\python.exe build_portable.py --python-dir "C:\\path\\to\\Python312"
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND = PROJECT_ROOT / 'backend'
VENV_SITE = BACKEND / 'venv' / 'Lib' / 'site-packages'
OUT_ROOT = PROJECT_ROOT / 'dist_portable'
APP_DIR_NAME = '杰哥硬字幕提取'

DEFAULT_PYTHON_DIR = Path(r'C:\Users\29406\AppData\Local\Programs\Python\Python312')

# 运行时不需要的目录
# 注意：*.dist-info 必须保留（只有 5MB）——fastapi / paddleocr / paddlex 启动时要用
# importlib.metadata 读自己的版本号，缺了会直接 ImportError。
IGNORE_SITE = shutil.ignore_patterns(
    '__pycache__', 'sqlglot', 'sqlglot-*', 'PyInstaller', 'pyinstaller-*',
    'pyinstaller_hooks_contrib', 'pyinstaller_hooks_contrib-*',
)
IGNORE_STD = shutil.ignore_patterns(
    '__pycache__', 'test', 'tests', 'idlelib', 'turtledemo', 'tcl', 'tkinter',
    'ensurepip', 'site-packages',
)

LAUNCHER = '''@echo off
rem 只用 ASCII 写批处理代码，避免 cmd 在不同代码页下解析中文出错
cd /d "%~dp0"
title Jiege Hard-Subtitle Extractor
if not exist "runtime\\python.exe" (
  echo [ERROR] runtime folder missing. Please extract the whole archive again.
  pause
  exit /b 1
)
"runtime\\python.exe" "backend\\desktop.py"
pause
'''

DEBUG_LAUNCHER = '''@echo off
cd /d "%~dp0"
title Jiege Hard-Subtitle Extractor (debug)
"runtime\\python.exe" "backend\\desktop.py" --diag
echo.
echo ---------------------------------------------------------------
echo If the service failed to start, the reason is above.
echo Close this window when done.
pause
'''

README_TXT = '''杰哥硬字幕提取 · 桌面版 使用说明
================================================================

一、启动（不弹窗口，用你自己的浏览器）
  双击「启动 杰哥硬字幕提取.bat」，会出现一个黑色窗口，等 5~20 秒
  （首次启动要初始化 + 加载模型），窗口里会显示：

        请在浏览器打开：  http://127.0.0.1:8800

  这个地址会自动复制到剪贴板，直接粘贴到浏览器（Edge / Chrome 都行）打开即可。
  ★ 黑色窗口必须一直开着，关掉它就等于退出软件。
  ★ 如果显示的是 8801/8802 等，说明 8800 被占用了，按显示的地址打开即可。
  ★ 出问题就双击「调试启动.bat」，它会打印路径自检信息，方便把错误发给我。

二、使用
  1. 点「点击或拖拽视频到此处上传」，选择本地视频（mp4 / mkv / flv / avi / mov 等）
  2. 上传完成后，在预览图上按住鼠标左键拖拽，框选字幕所在区域
     —— 框选能让识别又快又准；不框选则全屏检测
  3. 右侧选好「字幕语言」（默认简体中文）和「识别模式」（默认快速），点「开始提取」
  4. 完成后在「结果下载」里预览或下载 SRT，或点「校对」逐句改错字

三、校对（改错字）
  左边播放视频，右边字幕会跟着高亮当前这句。
  · 单击某一行 = 视频跳到这句
  · 双击某一行文字 = 直接编辑（回车或点空白处结束）
  改完点「保存修改」，再点「导出 SRT」/「导出 TXT」即可。

四、数据与迁移
  所有数据都在软件文件夹内：
      backend\\data\\zimu.db      任务记录
      backend\\data\\uploads\\    上传的视频
      backend\\data\\outputs\\    提取出的字幕
      backend\\data\\logs\\       运行日志
  换电脑：整个文件夹拷过去就能继续用。
  想恢复出厂状态：删掉 backend\\data 整个目录，下次启动会自动重建。

五、常见问题
  1. 双击没反应：看 backend\\data\\logs\\desktop.log；或用「调试启动.bat」看报错。
  2. 提示缺少 WebView2 运行库：Win10/11 一般自带；若没有，安装
     https://developer.microsoft.com/microsoft-edge/webview2/
  3. 提取慢：纯 CPU 识别，视频越长越慢。建议框选字幕区域 + 用「快速」模式。
  4. 杀毒软件误报：本软件是打包好的 Python 程序，若被拦截请加白名单。
  5. 软件路径和视频文件名建议不要带特殊符号。

六、系统要求
  Windows 10 / 11 64 位，建议 4 核以上 CPU、8GB 以上内存。
  无需安装 Python、MySQL 或任何运行环境。
'''


def dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1024 / 1024


def copy_tree(src: Path, dst: Path, ignore=None, label=''):
    if not src.exists():
        print(f'  [跳过] {label or src.name}：源目录不存在 {src}')
        return
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
    print(f'  [完成] {label or src.name:28} {dir_size_mb(dst):8.0f} MB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--python-dir', default=str(DEFAULT_PYTHON_DIR),
                    help='基础 Python 3.12 安装目录（复制它作为便携运行时）')
    ap.add_argument('--out', default=str(OUT_ROOT), help='输出根目录')
    args = ap.parse_args()

    py_dir = Path(args.python_dir)
    out_root = Path(args.out)
    target = out_root / APP_DIR_NAME

    print('=' * 70)
    print('打包 杰哥硬字幕提取 · Windows 便携版')
    print('=' * 70)

    if not (py_dir / 'python.exe').exists():
        print(f'[错误] 找不到基础 Python：{py_dir}')
        return 1
    if not VENV_SITE.exists():
        print(f'[错误] 找不到 venv 依赖目录：{VENV_SITE}')
        return 1
    if not (PROJECT_ROOT / 'frontend' / 'dist' / 'index.html').exists():
        print('[错误] 缺少前端构建产物 frontend/dist，请先在 frontend 目录执行 npm run build')
        return 1

    t0 = time.time()
    if target.exists():
        print(f'清理旧产物：{target}')
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    # 1. 便携 Python 运行时
    print('\n[1/5] 复制 Python 运行时（标准库 + 解释器）')
    runtime = target / 'runtime'
    shutil.copytree(py_dir, runtime, ignore=IGNORE_STD, dirs_exist_ok=True)
    # 用项目 venv 里装好的依赖覆盖运行时的 site-packages
    site_dst = runtime / 'Lib' / 'site-packages'
    if site_dst.exists():
        shutil.rmtree(site_dst)
    copy_tree(VENV_SITE, site_dst, ignore=IGNORE_SITE, label='第三方依赖 site-packages')

    # 2. 后端
    print('\n[2/5] 复制后端程序与模型')
    be = target / 'backend'
    be.mkdir(parents=True, exist_ok=True)
    copy_tree(BACKEND / 'app', be / 'app',
              ignore=shutil.ignore_patterns('__pycache__'), label='后端源码 app')
    copy_tree(BACKEND / 'configs', be / 'configs',
              ignore=shutil.ignore_patterns('__pycache__'), label='configs')
    copy_tree(BACKEND / 'interface', be / 'interface',
              ignore=shutil.ignore_patterns('__pycache__'), label='界面文案 interface')
    copy_tree(BACKEND / 'models', be / 'models', label='OCR 模型 models/V5')
    copy_tree(BACKEND / 'subfinder' / 'windows', be / 'subfinder' / 'windows',
              label='VideoSubFinder(Windows)')
    shutil.copy2(BACKEND / 'desktop.py', be / 'desktop.py')
    print(f'  [完成] desktop.py')

    # 3. 前端
    print('\n[3/5] 复制前端页面')
    copy_tree(PROJECT_ROOT / 'frontend' / 'dist', target / 'frontend' / 'dist', label='前端页面')

    # 4. 启动器与说明
    print('\n[4/5] 写启动器与使用说明')
    (target / '启动 杰哥硬字幕提取.bat').write_text(LAUNCHER, encoding='utf-8')
    (target / '调试启动.bat').write_text(DEBUG_LAUNCHER, encoding='utf-8')
    (target / '使用说明.txt').write_text(README_TXT, encoding='utf-8')
    print('  [完成] 启动器 x2 + 使用说明.txt')

    # 5. 汇总
    total = dir_size_mb(target)
    print('\n[5/5] 打包完成')
    print('-' * 70)
    print(f'输出目录 : {target}')
    print(f'总体积   : {total:.0f} MB')
    print(f'耗时     : {time.time() - t0:.0f} 秒')
    print('-' * 70)
    print('提示：发给别人时把整个文件夹压缩成 zip 即可，对方解压后双击'
          '「启动 杰哥硬字幕提取.bat」。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
