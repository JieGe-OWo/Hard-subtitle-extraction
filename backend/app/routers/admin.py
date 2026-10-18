import random
import time

from fastapi import APIRouter, Depends, HTTPException

from app import models
from app.config import ACTIVATION_CODE_LENGTH
from app.deps import get_admin_user
from app.schemas import GenerateCodesRequest, UpdateUserRequest

router = APIRouter(prefix='/api/admin', tags=['admin'], dependencies=[Depends(get_admin_user)])


@router.get('/dashboard')
def dashboard(admin=Depends(get_admin_user)):
    conn = models.get_conn()
    try:
        user_total = conn.execute('SELECT COUNT(*) c FROM users WHERE role = ?', ('user',)).fetchone()['c']
        user_active = conn.execute(
            "SELECT COUNT(*) c FROM users WHERE role = ? AND status = 'active'", ('user',)).fetchone()['c']
        user_pending = conn.execute(
            "SELECT COUNT(*) c FROM users WHERE role = ? AND status = 'pending'", ('user',)).fetchone()['c']
        user_disabled = conn.execute(
            "SELECT COUNT(*) c FROM users WHERE role = ? AND status = 'disabled'", ('user',)).fetchone()['c']
        code_total = conn.execute('SELECT COUNT(*) c FROM activation_codes').fetchone()['c']
        code_used = conn.execute('SELECT COUNT(*) c FROM activation_codes WHERE used_by IS NOT NULL').fetchone()['c']
        task_total = conn.execute('SELECT COUNT(*) c FROM tasks').fetchone()['c']
        task_done = conn.execute("SELECT COUNT(*) c FROM tasks WHERE status = 'completed'").fetchone()['c']
        task_running = conn.execute("SELECT COUNT(*) c FROM tasks WHERE status = 'running'").fetchone()['c']
        recent_users = [dict(r) for r in conn.execute(
            'SELECT id, email, status, created_at, activated_at FROM users WHERE role = ? '
            'ORDER BY created_at DESC LIMIT 10', ('user',)).fetchall()]
        recent_tasks = [dict(r) for r in conn.execute(
            'SELECT t.*, u.email FROM tasks t LEFT JOIN users u ON u.id = t.user_id '
            'ORDER BY t.created_at DESC LIMIT 10').fetchall()]
    finally:
        conn.close()
    return {
        'users': {'total': user_total, 'active': user_active, 'pending': user_pending, 'disabled': user_disabled},
        'codes': {'total': code_total, 'used': code_used, 'unused': code_total - code_used},
        'tasks': {'total': task_total, 'completed': task_done, 'running': task_running},
        'recent_users': recent_users,
        'recent_tasks': recent_tasks,
    }


# ---------------- 激活码管理 ----------------

@router.get('/codes')
def list_codes(status: str = 'all', keyword: str = '', page: int = 1, page_size: int = 20,
               admin=Depends(get_admin_user)):
    conn = models.get_conn()
    try:
        where = ['1 = 1']
        args = []
        if status == 'used':
            where.append('used_by IS NOT NULL')
        elif status == 'unused':
            where.append('used_by IS NULL')
        elif status == 'disabled':
            where.append('enabled = 0')
        elif status == 'expired':
            where.append('expires_at IS NOT NULL AND expires_at < ?')
            args.append(time.time())
        if keyword:
            where.append('(code LIKE ? OR note LIKE ?)')
            args += [f'%{keyword}%', f'%{keyword}%']
        where_sql = ' AND '.join(where)
        total = conn.execute(
            f'SELECT COUNT(*) c FROM activation_codes WHERE {where_sql}', args).fetchone()['c']
        rows = conn.execute(
            f'''SELECT ac.*, u.email AS used_email FROM activation_codes ac
                LEFT JOIN users u ON u.id = ac.used_by
                WHERE {where_sql} ORDER BY ac.id DESC LIMIT ? OFFSET ?''', args + [page_size, (page - 1) * page_size]).fetchall()
    finally:
        conn.close()
    return {'total': total, 'page': page, 'page_size': page_size, 'items': [dict(r) for r in rows]}


@router.post('/codes')
def generate_codes(body: GenerateCodesRequest, admin=Depends(get_admin_user)):
    if body.count < 1 or body.count > 500:
        raise HTTPException(status_code=400, detail='每次生成数量需在 1-500 之间')
    expires_at = time.time() + body.expires_in_days * 86400
    created = []
    for _ in range(body.count):
        while True:
            code = body.prefix + ''.join(random.choices(
                'ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=ACTIVATION_CODE_LENGTH))
            if not models.get_activation_code(code):
                break
        models.create_activation_code(code, body.note, admin['id'], expires_at)
        created.append(code)
    return {'message': f'成功生成 {len(created)} 个激活码', 'codes': created}


@router.post('/codes/custom')
def add_custom_code(body: dict, admin=Depends(get_admin_user)):
    from app.schemas import CustomCodeRequest
    req = CustomCodeRequest(**body)
    if models.get_activation_code(req.code):
        raise HTTPException(status_code=400, detail='该激活码已存在')
    expires_at = time.time() + req.expires_in_days * 86400
    code_id = models.create_activation_code(req.code, req.note, admin['id'], expires_at)
    return {'message': '添加成功', 'id': code_id, 'code': req.code}


@router.patch('/codes/{code_id}')
def update_code(code_id: int, body: dict, admin=Depends(get_admin_user)):
    conn = models.get_conn()
    try:
        row = conn.execute('SELECT * FROM activation_codes WHERE id = ?', (code_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='激活码不存在')
        if 'enabled' in body:
            conn.execute('UPDATE activation_codes SET enabled = ? WHERE id = ?', (1 if body['enabled'] else 0, code_id))
        if 'note' in body:
            conn.execute('UPDATE activation_codes SET note = ? WHERE id = ?', (str(body['note']), code_id))
        if 'expires_at' in body:
            conn.execute('UPDATE activation_codes SET expires_at = ? WHERE id = ?',
                         (time.time() + int(body['expires_at']) * 86400, code_id))
        conn.commit()
    finally:
        conn.close()
    return {'message': '更新成功'}


@router.delete('/codes/{code_id}')
def delete_code(code_id: int, admin=Depends(get_admin_user)):
    conn = models.get_conn()
    try:
        row = conn.execute('SELECT * FROM activation_codes WHERE id = ?', (code_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='激活码不存在')
        if row['used_by'] is not None:
            raise HTTPException(status_code=400, detail='已被使用的激活码不可删除')
        conn.execute('DELETE FROM activation_codes WHERE id = ?', (code_id,))
        conn.commit()
    finally:
        conn.close()
    return {'message': '已删除'}


# ---------------- 用户管理 ----------------

@router.get('/users')
def list_users(keyword: str = '', status: str = 'all', page: int = 1, page_size: int = 20,
               admin=Depends(get_admin_user)):
    conn = models.get_conn()
    try:
        where = ["role = 'user'"]
        args = []
        if keyword:
            where.append('email LIKE ?')
            args.append(f'%{keyword}%')
        if status in ('pending', 'active', 'disabled'):
            where.append('status = ?')
            args.append(status)
        where_sql = ' AND '.join(where)
        total = conn.execute(f'SELECT COUNT(*) c FROM users WHERE {where_sql}', args).fetchone()['c']
        rows = conn.execute(
            f'SELECT id, email, status, created_at, activated_at, last_login_at FROM users '
            f'WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?', args + [page_size, (page - 1) * page_size]).fetchall()
    finally:
        conn.close()
    return {'total': total, 'page': page, 'page_size': page_size, 'items': [dict(r) for r in rows]}


@router.patch('/users/{user_id}')
def update_user(user_id: int, body: UpdateUserRequest, admin=Depends(get_admin_user)):
    target = models.get_user_by_id(user_id)
    if not target or target['role'] != 'user':
        raise HTTPException(status_code=404, detail='用户不存在')
    if body.status:
        if body.status not in ('pending', 'active', 'disabled'):
            raise HTTPException(status_code=400, detail='无效的状态')
        conn = models.get_conn()
        try:
            conn.execute('UPDATE users SET status = ?' + (', activated_at = ?' if body.status == 'active' else '')
                         + ' WHERE id = ?', ('active', time.time(), user_id) if body.status == 'active' else (body.status, user_id))
            conn.commit()
        finally:
            conn.close()
    return {'message': '更新成功'}


@router.get('/tasks')
def admin_tasks(page: int = 1, page_size: int = 20, admin=Depends(get_admin_user)):
    conn = models.get_conn()
    try:
        total = conn.execute('SELECT COUNT(*) c FROM tasks').fetchone()['c']
        rows = conn.execute(
            'SELECT t.*, u.email FROM tasks t LEFT JOIN users u ON u.id = t.user_id '
            'ORDER BY t.created_at DESC LIMIT ? OFFSET ?', (page_size, (page - 1) * page_size)).fetchall()
    finally:
        conn.close()
    return {'total': total, 'page': page, 'page_size': page_size, 'items': [dict(r) for r in rows]}
