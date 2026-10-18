import time

from app.database import get_conn, init_db


def init_admin():
    """首次启动时创建固定管理员账号"""
    from app.config import ADMIN_EMAIL, ADMIN_PASSWORD
    from app.security import hash_password
    conn = get_conn()
    try:
        row = conn.execute('SELECT id FROM users WHERE role = ?', ('admin',)).fetchone()
        if row:
            return
        exist = conn.execute('SELECT id FROM users WHERE email = ?', (ADMIN_EMAIL,)).fetchone()
        if exist:
            conn.execute('UPDATE users SET role = ?, status = ? WHERE id = ?', ('admin', 'active', exist['id']))
        else:
            conn.execute(
                'INSERT INTO users(email, password_hash, role, status, created_at, activated_at) VALUES(?,?,?,?,?,?)',
                (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), 'admin', 'active', time.time(), time.time()))
        conn.commit()
    finally:
        conn.close()


def ensure_local_user(email: str, password: str = 'local-desktop-user'):
    """桌面免登录模式：确保存在一个本地用户并返回它（不存在就建，存在就修正为可用状态）"""
    from app.security import hash_password
    conn = get_conn()
    try:
        row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row is None:
            conn.execute(
                'INSERT INTO users(email, password_hash, role, status, created_at, activated_at, subscription_expire_at) '
                'VALUES(?,?,?,?,?,?,?)',
                (email, hash_password(password), 'admin', 'active',
                 time.time(), time.time(), 0))
            conn.commit()
        elif row['role'] != 'admin' or row['status'] != 'active':
            conn.execute('UPDATE users SET role = ?, status = ?, activated_at = ? WHERE id = ?',
                         ('admin', 'active', time.time(), row['id']))
            conn.commit()
        return conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    finally:
        conn.close()


def init_local_user():
    """桌面版启动时调用：只准备本地用户，不建网页版管理员"""
    from app.config import DESKTOP_USER_EMAIL
    return ensure_local_user(DESKTOP_USER_EMAIL)


def get_user_by_email(email: str):
    conn = get_conn()
    try:
        return conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_conn()
    try:
        return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    finally:
        conn.close()


def create_user(email: str, password_hash: str) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            'INSERT INTO users(email, password_hash, role, status, created_at) VALUES(?,?,?,?,?)',
            (email, password_hash, 'user', 'pending', time.time()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def activate_user(user_id: int):
    conn = get_conn()
    try:
        conn.execute('UPDATE users SET status = ?, activated_at = ? WHERE id = ?', ('active', time.time(), user_id))
        conn.commit()
    finally:
        conn.close()


def update_last_login(user_id: int):
    conn = get_conn()
    try:
        conn.execute('UPDATE users SET last_login_at = ? WHERE id = ?', (time.time(), user_id))
        conn.commit()
    finally:
        conn.close()


def create_email_code(email: str, code: str, purpose: str, ttl: int) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            'INSERT INTO email_codes(email, code, purpose, created_at, expires_at) VALUES(?,?,?,?,?)',
            (email, code, purpose, time.time(), time.time() + ttl))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_valid_email_code(email: str, purpose: str):
    conn = get_conn()
    try:
        return conn.execute(
            'SELECT * FROM email_codes WHERE email = ? AND purpose = ? AND used_at IS NULL ORDER BY id DESC LIMIT 1',
            (email, purpose)).fetchone()
    finally:
        conn.close()


def bump_email_code_attempts(code_id: int):
    conn = get_conn()
    try:
        conn.execute('UPDATE email_codes SET attempts = attempts + 1 WHERE id = ?', (code_id,))
        conn.commit()
    finally:
        conn.close()


def mark_email_code_used(code_id: int):
    conn = get_conn()
    try:
        conn.execute('UPDATE email_codes SET used_at = ? WHERE id = ?', (time.time(), code_id))
        conn.commit()
    finally:
        conn.close()


def create_activation_code(code: str, note: str, created_by: int, expires_at):
    conn = get_conn()
    try:
        cur = conn.execute(
            'INSERT INTO activation_codes(code, note, created_by, created_at, expires_at) VALUES(?,?,?,?,?)',
            (code, note, created_by, time.time(), expires_at))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_activation_code(code: str):
    conn = get_conn()
    try:
        return conn.execute('SELECT * FROM activation_codes WHERE code = ?', (code,)).fetchone()
    finally:
        conn.close()


def mark_activation_used(code_id: int, user_id: int):
    conn = get_conn()
    try:
        conn.execute('UPDATE activation_codes SET used_by = ?, used_at = ? WHERE id = ?', (user_id, time.time(), code_id))
        conn.commit()
    finally:
        conn.close()


def create_task_record(task_id: str, user_id: int, video_name: str, options_str: str):
    conn = get_conn()
    try:
        conn.execute(
            'INSERT INTO tasks(id, user_id, video_name, status, options, created_at) VALUES(?,?,?,?,?,?)',
            (task_id, user_id, video_name, 'pending', options_str, time.time()))
        conn.commit()
    finally:
        conn.close()


def get_task_record(task_id: str):
    conn = get_conn()
    try:
        return conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    finally:
        conn.close()


def list_task_records(user_id: int, limit: int = 100):
    conn = get_conn()
    try:
        return conn.execute(
            'SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?', (user_id, limit)).fetchall()
    finally:
        conn.close()


def list_all_task_records(limit: int = 500):
    conn = get_conn()
    try:
        return conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
    finally:
        conn.close()


def update_task_record(task_id: str, **fields):
    if not fields:
        return
    conn = get_conn()
    try:
        sets = ', '.join(f'{k} = ?' for k in fields)
        conn.execute(f'UPDATE tasks SET {sets} WHERE id = ?', (*fields.values(), task_id))
        conn.commit()
    finally:
        conn.close()
