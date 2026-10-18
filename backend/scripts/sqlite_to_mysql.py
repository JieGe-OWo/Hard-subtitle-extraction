"""把现有 SQLite 数据导出为 MySQL 可执行的 SQL（zimu-data.sql / zimu-all.sql）。

用法（项目根目录）：
    backend\\venv\\Scripts\\python backend/scripts/sqlite_to_mysql.py
    backend\\venv\\Scripts\\python backend/scripts/sqlite_to_mysql.py --all

默认输出 zimu-data.sql（只含数据，自带 CREATE DATABASE + USE，可重复执行）；
加 --all 额外输出 zimu-all.sql（建库 + 建表 + 数据，一个文件搞定，推荐给图形化工具用）。

导出的表：users / email_codes / activation_codes / tasks
（pay_orders 是预留表，当前无数据，不导出。）

说明：INSERT 使用 INSERT IGNORE，重复执行只会跳过已存在的行，不会整批报错。
"""
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND = os.path.join(ROOT, 'backend')
DEFAULT_DB = os.path.join(BACKEND, 'data', 'zimu.db')
DEFAULT_OUT = os.path.join(ROOT, 'zimu-data.sql')
ALL_OUT = os.path.join(ROOT, 'zimu-all.sql')
DB_NAME = os.getenv('DB_NAME', 'zimu')

TABLES = [
    'users',
    'email_codes',
    'activation_codes',
    'tasks',
]

HEADER = [
    '-- =====================================================================',
    '-- ZiMu 数据导出（由 backend/scripts/sqlite_to_mysql.py 生成）',
    f'-- 生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}',
    f'-- 目标数据库：`{DB_NAME}`（脚本会自动创建，无需先手动建库）',
    '-- 可重复执行：使用 INSERT IGNORE，已存在的行会被跳过。',
    '-- =====================================================================',
    '',
    f'CREATE DATABASE IF NOT EXISTS `{DB_NAME}` '
    'DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;',
    '',
    f'USE `{DB_NAME}`;',
    '',
    '-- 强制本次连接的字符集，避免图形化工具默认 latin1 导致中文报错',
    'SET NAMES utf8mb4;',
    '',
]


def sql_literal(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    s = str(v)
    return "'" + s.replace('\\', '\\\\').replace("'", "''") + "'"


def mysql_schema():
    """从 app.database 取 MySQL 建表语句，保证与后端自动建表完全一致"""
    if BACKEND not in sys.path:
        sys.path.insert(0, BACKEND)
    try:
        from app.database import MYSQL_SCHEMA
        return [s.strip().rstrip(';') + ';' for s in MYSQL_SCHEMA]
    except Exception as e:  # noqa: BLE001
        print(f'[warn] 读取建表语句失败，zimu-all.sql 将不含建表部分：{e}')
        return []


def build_data_lines(conn):
    lines = []
    for table in TABLES:
        cols = [r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
        rows = conn.execute(f'SELECT * FROM {table}').fetchall()
        if not rows:
            continue
        col_sql = ', '.join(f'`{c}`' for c in cols)
        lines.append(f'-- ---------- {table}（{len(rows)} 行） ----------')
        for start in range(0, len(rows), 200):
            batch = rows[start:start + 200]
            values = ['(' + ', '.join(sql_literal(row[c]) for c in cols) + ')' for row in batch]
            lines.append(f'INSERT IGNORE INTO `{table}` ({col_sql}) VALUES')
            lines.append(',\n'.join(values) + ';')
            lines.append('')
    return lines


def write_sql(path, lines):
    # newline='\n' 保证固定 LF，避免不同工具对 CRLF 的处理差异
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    print(f'已导出 -> {path}')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    with_all = '--all' in sys.argv
    db_path = args[0] if args else DEFAULT_DB
    out_path = args[1] if len(args) > 1 else DEFAULT_OUT

    if not os.path.isfile(db_path):
        print(f'SQLite 数据库不存在：{db_path}')
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    data_lines = build_data_lines(conn)
    conn.close()

    write_sql(out_path, HEADER + data_lines)

    if with_all:
        schema = mysql_schema()
        all_lines = HEADER + [
            '-- ---------- 建表（来自 backend/app/database.py，与后端一致） ----------',
            '',
        ] if schema else list(HEADER)
        if schema:
            all_lines += schema + ['']
            all_lines += ['-- ---------- 数据 ----------', '']
        all_lines += data_lines
        write_sql(ALL_OUT, all_lines)
    return 0


if __name__ == '__main__':
    sys.exit(main())
