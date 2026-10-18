"""数据库访问层（双驱动：MySQL 默认 / SQLite 兼容）。

默认走 MySQL（DB_TYPE=mysql）：连 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME。
本地没有 MySQL、只想先跑起来或做测试时，设 DB_TYPE=sqlite 用内置 SQLite
（backend/data/zimu.db）。

对上层保持与旧 sqlite3 一致的用法：

    conn = get_conn()
    row = conn.execute('SELECT ... WHERE x = ?', (v,)).fetchone()
    conn.commit()
    conn.close()

所有 SQL 沿用 ? 占位符，MySQL 后端会自动翻译成 %s；
行对象两种后端都支持 row['列名'] 与 dict(row)。
"""
import sqlite3

from app.config import (DB_HOST, DB_NAME, DB_PASSWORD, DB_PATH, DB_PORT,
                        DB_TYPE, DB_USER)

# ---------------- 建表语句（幂等） ----------------

MYSQL_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(16) NOT NULL DEFAULT 'user',
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        subscription_expire_at DOUBLE NOT NULL DEFAULT 0 COMMENT '订阅到期时间(unix秒)，0=不受限/未订阅',
        created_at DOUBLE NOT NULL,
        activated_at DOUBLE NULL,
        last_login_at DOUBLE NULL,
        UNIQUE KEY uq_users_email (email(191))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS email_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        code VARCHAR(16) NOT NULL,
        purpose VARCHAR(32) NOT NULL,
        created_at DOUBLE NOT NULL,
        expires_at DOUBLE NOT NULL,
        attempts INT NOT NULL DEFAULT 0,
        used_at DOUBLE NULL,
        KEY idx_email_purpose (email(150), purpose(32))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS activation_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(64) NOT NULL,
        enabled TINYINT NOT NULL DEFAULT 1,
        note VARCHAR(255) NOT NULL DEFAULT '',
        created_by INT NULL,
        created_at DOUBLE NOT NULL,
        expires_at DOUBLE NULL,
        used_by INT NULL,
        used_at DOUBLE NULL,
        UNIQUE KEY uq_activation_code (code),
        KEY idx_activation_used (used_by)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id VARCHAR(40) NOT NULL PRIMARY KEY,
        user_id INT NOT NULL,
        video_name VARCHAR(255) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        progress_frame DOUBLE NOT NULL DEFAULT 0,
        progress_ocr DOUBLE NOT NULL DEFAULT 0,
        progress_post DOUBLE NOT NULL DEFAULT 0,
        error TEXT NULL,
        output_srt VARCHAR(512) NOT NULL DEFAULT '',
        output_txt VARCHAR(512) NOT NULL DEFAULT '',
        options TEXT NULL,
        created_at DOUBLE NOT NULL,
        finished_at DOUBLE NULL,
        KEY idx_tasks_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    # 支付订单（预留）：后续「充值一个月使用权限」直接使用，当前版本不读写
    """CREATE TABLE IF NOT EXISTS pay_orders (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        order_no VARCHAR(40) NOT NULL COMMENT '业务订单号',
        user_id INT NOT NULL COMMENT 'users.id',
        plan VARCHAR(16) NOT NULL DEFAULT 'month' COMMENT '套餐：month=一个月',
        days INT NOT NULL DEFAULT 30 COMMENT '充值时长(天)',
        amount_cents INT NOT NULL DEFAULT 0 COMMENT '金额(分)',
        status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/cancelled',
        channel VARCHAR(32) NOT NULL DEFAULT '' COMMENT '支付渠道 alipay/wechat/manual...',
        created_at DOUBLE NOT NULL,
        paid_at DOUBLE NULL,
        expire_at DOUBLE NULL COMMENT '支付成功后写入的订阅到期时间快照',
        note VARCHAR(255) NOT NULL DEFAULT '',
        UNIQUE KEY uq_pay_order_no (order_no),
        KEY idx_pay_user (user_id),
        KEY idx_pay_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付订单表（预留，供充值一个月使用权使用）'""",
]

SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pending',
        subscription_expire_at REAL NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        activated_at REAL,
        last_login_at REAL
    )""",
    """CREATE TABLE IF NOT EXISTS email_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        purpose TEXT NOT NULL,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        used_at REAL
    )""",
    """CREATE TABLE IF NOT EXISTS activation_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        note TEXT DEFAULT '',
        created_by INTEGER,
        created_at REAL NOT NULL,
        expires_at REAL,
        used_by INTEGER,
        used_at REAL,
        FOREIGN KEY(used_by) REFERENCES users(id)
    )""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        video_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        progress_frame REAL DEFAULT 0,
        progress_ocr REAL DEFAULT 0,
        progress_post REAL DEFAULT 0,
        error TEXT,
        output_srt TEXT,
        output_txt TEXT,
        options TEXT,
        created_at REAL NOT NULL,
        finished_at REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""",
    """CREATE TABLE IF NOT EXISTS pay_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        plan TEXT NOT NULL DEFAULT 'month',
        days INTEGER NOT NULL DEFAULT 30,
        amount_cents INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        channel TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        paid_at REAL,
        expire_at REAL,
        note TEXT NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_activation_used ON activation_codes(used_by)",
]

# 旧 SQLite 库升级用：新增列
SQLITE_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN subscription_expire_at REAL NOT NULL DEFAULT 0",
]


class DBConn:
    """同时兼容 sqlite3 / pymysql 的最小连接包装。"""

    def __init__(self, raw, backend: str):
        self._raw = raw
        self._backend = backend
        self._cursor = None

    def execute(self, sql: str, params=()):
        if self._backend == 'mysql':
            cursor = self._raw.cursor()
            cursor.execute(sql.replace('?', '%s'), tuple(params))
            self._cursor = cursor
        else:
            self._cursor = self._raw.execute(sql, params)
        return self

    def fetchone(self):
        if self._cursor is None:
            return None
        return self._cursor.fetchone()

    def fetchall(self):
        if self._cursor is None:
            return []
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid if self._cursor is not None else None

    @property
    def rowcount(self):
        return self._cursor.rowcount if self._cursor is not None else -1

    def commit(self):
        self._raw.commit()

    def rollback(self):
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is not None:
            self.rollback()
        self.close()
        return False


def get_conn() -> DBConn:
    """每次调用新建一个连接（与旧 sqlite3 用法一致，用完 close）。"""
    if DB_TYPE == 'mysql':
        import pymysql
        raw = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False, connect_timeout=5,
        )
        return DBConn(raw, 'mysql')

    raw = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    return DBConn(raw, 'sqlite')


def init_db():
    """启动时建表（幂等）。MySQL 侧的表结构以用户执行的 zimu.sql 为准，这里兜底。"""
    conn = get_conn()
    try:
        if DB_TYPE == 'mysql':
            for stmt in MYSQL_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        else:
            for stmt in SQLITE_SCHEMA:
                conn.execute(stmt)
            conn.commit()
            # 旧库升级：users 表补订阅到期字段
            cols = {r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'subscription_expire_at' not in cols:
                for stmt in SQLITE_MIGRATIONS:
                    conn.execute(stmt)
                conn.commit()
    finally:
        conn.close()
