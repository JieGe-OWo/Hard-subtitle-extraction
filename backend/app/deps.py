from fastapi import Depends, Header, HTTPException, Query

from app.database import get_conn
from app.security import decode_token


def get_current_user(authorization: str = Header(None), token: str = Query(None)):
    """从 Authorization 头取令牌；也支持 ?token= 查询参数，
    因为 <video>/<img> 直链没法带请求头（视频流、预览图需要）。"""
    auth = (authorization or '').strip()
    if not auth.lower().startswith('bearer '):
        if not token:
            raise HTTPException(status_code=401, detail='未登录')
        auth = 'Bearer ' + token
    payload = decode_token(auth[7:].strip())
    if payload is None or 'sub' not in payload:
        raise HTTPException(status_code=401, detail='登录已过期，请重新登录')
    conn = get_conn()
    try:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (int(payload['sub']),)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=401, detail='账号不存在')
    if row['status'] == 'disabled':
        raise HTTPException(status_code=403, detail='账号已被禁用')
    return row


def get_admin_user(user=Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='需要管理员权限')
    return user


def get_active_user(user=Depends(get_current_user)):
    """必须已激活（使用过有效激活码）的用户"""
    if user['status'] != 'active':
        raise HTTPException(status_code=403, detail='账号尚未激活，请输入有效激活码后使用')
    return user
