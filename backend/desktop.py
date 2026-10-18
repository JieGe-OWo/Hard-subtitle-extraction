"""杰哥硬字幕提取 · 桌面版启动器

启动本地服务，然后在控制台显示访问地址（同时复制到剪贴板），
你自己在浏览器里打开即可。不弹任何浏览器窗口。

用法：
    python desktop.py             # 启动服务并显示地址（默认，推荐）
    python desktop.py --browser   # 启动服务后顺便用默认浏览器打开
    python desktop.py --port 8800 # 指定端口
    python desktop.py --diag      # 只做路径/依赖自检后退出
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
LOG_DIR = BACKEND_DIR / 'data' / 'logs'
TITLE = '杰哥硬字幕提取'
PORT_START = 8800
PORT_TRIES = 22


def log(msg: str):
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / 'desktop.log', 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def copy_to_clipboard(text: str) -> bool:
    """把地址塞进剪贴板，省得手打"""
    try:
        subprocess.run(['clip'], input=text.encode('utf-8'), check=False,
                       timeout=5, shell=False)
        return True
    except Exception:
        return False


def find_running():
    """如果已有本软件实例在跑，返回它的地址（避免重复启动抢端口）"""
    for port in range(PORT_START, PORT_START + PORT_TRIES):
        url = f'http://127.0.0.1:{port}'
        try:
            with urllib.request.urlopen(url + '/api/app-info', timeout=0.6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if data.get('title') == TITLE:
                return url
        except Exception:
            continue
    return None


def wait_started(server, timeout: int = 180) -> bool:
    """等 uvicorn 真正绑定成功（不能用 HTTP 探测代替，否则会误连到旧实例）"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if getattr(server, 'started', False):
            return True
        if getattr(server, 'should_exit', False):
            return False
        time.sleep(0.15)
    return False


def wait_ready(url: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + '/api/health', timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def show_banner(url: str, running: bool = False):
    line = '=' * 52
    print('', flush=True)
    print(line, flush=True)
    if running:
        print(f'  {TITLE} 已经在运行', flush=True)
    else:
        print(f'  {TITLE} 已启动', flush=True)
    print(line, flush=True)
    print('', flush=True)
    print(f'  请在浏览器打开：  {url}', flush=True)
    print('', flush=True)
    if copy_to_clipboard(url):
        print('  （地址已复制到剪贴板，直接在浏览器地址栏粘贴即可）', flush=True)
    print('', flush=True)
    print('  说明：', flush=True)
    print('   · 本窗口必须保持打开，关掉窗口就等于退出软件', flush=True)
    print('   · 如果浏览器提示打不开，等几秒再刷新一次（首次加载模型较慢）', flush=True)
    print('', flush=True)
    print(line, flush=True)
    print('', flush=True)


def _serve_forever(server):
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    server.should_exit = True


def main():
    parser = argparse.ArgumentParser(description=f'{TITLE} 桌面版')
    parser.add_argument('--port', type=int, default=0, help='指定端口（默认 8800 起自动挑）')
    parser.add_argument('--browser', action='store_true', help='启动后用默认浏览器打开')
    parser.add_argument('--diag', action='store_true', help='只打印自检信息后退出')
    parser.add_argument('--no-window', action='store_true', help='（兼容参数，等价于默认行为）')
    args = parser.parse_args()

    # pywebview 等特性会用 argv[0] 推断根目录，这里统一钉成绝对路径
    sys.argv[0] = str(BACKEND_DIR / 'desktop.py')

    os.environ['DESKTOP_MODE'] = '1'
    os.environ.setdefault('DB_TYPE', 'sqlite')
    os.chdir(BACKEND_DIR)
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    log('=== 启动桌面版 ===')
    try:
        import uvicorn
        from app import runtime_paths
        from app.main import app
    except Exception:
        log('导入后端失败：\n' + traceback.format_exc())
        print('\n[启动失败] 后端加载出错，详情见 backend\\data\\logs\\desktop.log', flush=True)
        raise

    log(runtime_paths.summary())
    for line in runtime_paths.diagnostics():
        log('  ' + line)

    if args.diag:
        print(runtime_paths.summary())
        for line in runtime_paths.diagnostics():
            print('  ' + line)
        return

    # 已经在跑就直接给地址，避免开第二个实例抢端口
    running = find_running()
    if running and not args.port:
        log(f'检测到已有实例：{running}')
        show_banner(running, running=True)
        try:
            input('  按回车关闭此窗口…')
        except Exception:
            time.sleep(8)
        return

    candidates = ([args.port] if args.port else []) + \
        [p for p in range(PORT_START, PORT_START + PORT_TRIES) if p != args.port]
    server = None
    port = None
    for cand in candidates:
        srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=cand,
                                            log_level='warning', access_log=False))
        threading.Thread(target=srv.run, daemon=True, name='uvicorn').start()
        if wait_started(srv):
            server, port = srv, cand
            break
        srv.should_exit = True
        log(f'端口 {cand} 不可用，换下一个')
    if server is None:
        log('没有可用端口，启动失败')
        print('\n[启动失败] 8800-8821 端口都被占用了', flush=True)
        return

    url = f'http://127.0.0.1:{port}'
    if not wait_ready(url):
        log('服务启动超时')
        print('\n[启动失败] 服务启动超时，详情见 backend\\data\\logs\\desktop.log', flush=True)
        server.should_exit = True
        return
    log(f'本地服务就绪：{url}')

    show_banner(url)

    if args.browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    _serve_forever(server)


if __name__ == '__main__':
    main()
