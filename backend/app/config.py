import os
from pathlib import Path

from app import runtime_paths as RUNTIME_PATHS

# Paddle 环境变量（必须在 import paddle 前设置）
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
os.environ.setdefault('FLAGS_use_mkldnn', '0')
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'True')

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path):
    """极简 .env 加载（不引入额外依赖）。

    格式：KEY=VALUE，支持 # 注释、值两侧引号；已存在的真实环境变量优先，
    所以 `set DB_PASSWORD=xxx` 仍可覆盖 .env 里的值。
    """
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


# 必须在下面所有 os.getenv 之前加载，否则 .env 不生效
_load_env_file(BASE_DIR / '.env')

DATA_DIR = RUNTIME_PATHS.DATA_DIR
UPLOAD_DIR = DATA_DIR / 'uploads'
OUTPUT_DIR = DATA_DIR / 'outputs'
DB_PATH = DATA_DIR / 'zimu.db'

# 模型与 VideoSubFinder 目录（软件路径含中文时会自动走英文镜像，见 runtime_paths）
MODELS_DIR = RUNTIME_PATHS.MODELS_DIR
SUBFINDER_DIR = RUNTIME_PATHS.SUBFINDER_DIR

# 数据库（默认 MySQL，需先执行 zimu.sql 建库；本地无 MySQL 时可设 DB_TYPE=sqlite 用内置 SQLite）
DB_TYPE = os.getenv('DB_TYPE', 'mysql').lower()
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'zimu')

# 桌面版（便携软件）：免登录、无账号、内置 SQLite，由 desktop.py 启动时置 1
DESKTOP_MODE = os.getenv('DESKTOP_MODE', '0') == '1'
DESKTOP_USER_EMAIL = os.getenv('DESKTOP_USER_EMAIL', 'local@zimu.desktop')

SECRET_KEY = os.getenv('SECRET_KEY', 'zimu-subtitle-extractor-secret-key-change-in-prod')
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

APP_TITLE = '杰哥硬字幕提取'
APP_VERSION = '1.0.0'

# SMTP 邮件配置（未配置 SMTP_HOST 时为开发模式，验证码直接返回给前端）
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', '')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', '杰哥硬字幕提取')
SMTP_SSL = os.getenv('SMTP_SSL', '1') == '1'

# 固定管理员账号（首次启动时自动创建），邮箱需为真实可用的邮箱地址
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'zimuadminj8wfe@gmail.com')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin@123456')

# 注册邮箱验证码
EMAIL_CODE_TTL = 600
EMAIL_CODE_MAX_ATTEMPTS = 10

# 激活码
ACTIVATION_CODE_LENGTH = 16
ACTIVATION_CODE_TTL_DAYS = 30

CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]

MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', str(2 * 1024 * 1024 * 1024)))

for _d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
