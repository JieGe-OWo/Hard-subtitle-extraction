import random
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app import models
from app.config import (ACTIVATION_CODE_TTL_DAYS, DESKTOP_MODE,
                        EMAIL_CODE_MAX_ATTEMPTS, EMAIL_CODE_TTL)
from app.deps import get_current_user
from app.email_service import generate_code, send_email
from app.schemas import (ActivateRequest, GenerateCodesRequest, LoginRequest,
                         RegisterRequest, SendCodeRequest, TokenResponse)

router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/desktop-login', response_model=TokenResponse)
def desktop_login():
    """桌面版免登录：直接签发本地用户的令牌（仅在 DESKTOP_MODE 下可用）"""
    if not DESKTOP_MODE:
        raise HTTPException(status_code=404, detail='未启用桌面模式')
    from app.security import create_access_token
    user = models.init_local_user()
    return TokenResponse(access_token=create_access_token({'sub': user['id']}))


@router.post('/send-register-code')
def send_register_code(body: SendCodeRequest):
    email = str(body.email).lower()
    code = generate_code(6)
    sent = send_email(email, code)
    if not sent:
        print(f'[dev] 注册验证码 {email} -> {code}')
    models.create_email_code(email, code, 'register', EMAIL_CODE_TTL)
    return {
        'sent': sent,
        'dev': not sent,
        'code': None if sent else code,
        'message': '验证码已发送到邮箱' if sent else 'SMTP未配置，已进入开发模式，验证码见返回内容',
    }


@router.post('/register', response_model=TokenResponse)
def register(body: RegisterRequest):
    email = body.email.lower()
    if models.get_user_by_email(email):
        raise HTTPException(status_code=400, detail='该邮箱已注册，请直接登录')
    code_row = models.get_valid_email_code(email, 'register')
    if not code_row:
        raise HTTPException(status_code=400, detail='请先获取邮箱验证码')
    if code_row['expires_at'] < time.time():
        raise HTTPException(status_code=400, detail='验证码已过期，请重新获取')
    if code_row['attempts'] >= EMAIL_CODE_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail='尝试次数过多，请重新获取验证码')
    if code_row['code'] != body.code:
        models.bump_email_code_attempts(code_row['id'])
        raise HTTPException(status_code=400, detail='验证码不正确')
    models.mark_email_code_used(code_row['id'])
    from app.security import hash_password, create_access_token
    user_id = models.create_user(email, hash_password(body.password))
    return TokenResponse(access_token=create_access_token({'sub': user_id}))


@router.post('/login', response_model=TokenResponse)
def login(body: LoginRequest):
    from app.security import verify_password, create_access_token
    user = models.get_user_by_email(body.email.lower())
    if not user or not verify_password(body.password, user['password_hash']):
        raise HTTPException(status_code=400, detail='邮箱或密码不正确')
    if user['status'] == 'disabled':
        raise HTTPException(status_code=403, detail='账号已被禁用')
    models.update_last_login(user['id'])
    return TokenResponse(access_token=create_access_token({'sub': user['id']}))


@router.get('/me')
def me(user=Depends(get_current_user)):
    return {
        'id': user['id'],
        'email': user['email'],
        'role': user['role'],
        'status': user['status'],
        'created_at': user['created_at'],
        'activated_at': user['activated_at'],
        'last_login_at': user['last_login_at'],
    }


@router.post('/activate')
def activate(body: ActivateRequest, user=Depends(get_current_user)):
    if user['status'] == 'active':
        raise HTTPException(status_code=400, detail='账号已经激活')
    code_row = models.get_activation_code(body.code)
    if not code_row:
        raise HTTPException(status_code=400, detail='激活码不存在')
    if not code_row['enabled']:
        raise HTTPException(status_code=400, detail='激活码已停用')
    if code_row['used_by'] is not None:
        raise HTTPException(status_code=400, detail='激活码已被使用，每个激活码只能激活一个账号')
    if code_row['expires_at'] and code_row['expires_at'] < time.time():
        raise HTTPException(status_code=400, detail='激活码已过期')
    models.mark_activation_used(code_row['id'], user['id'])
    models.activate_user(user['id'])
    return {'message': '激活成功，现在可以使用字幕提取功能'}


@router.get('/activation/status')
def activation_status(user=Depends(get_current_user)):
    conn = models.get_conn()
    try:
        row = conn.execute(
            'SELECT ac.code, ac.used_at FROM activation_codes ac WHERE ac.used_by = ?', (user['id'],)).fetchone()
    finally:
        conn.close()
    return {
        'status': user['status'],
        'code': row['code'] if row else None,
        'activated_at': row['used_at'] if row else None,
    }
