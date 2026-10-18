import hashlib
import os
import time

from app.config import SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000)
    return 'pbkdf2_sha256$600000$' + salt.hex() + '$' + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split('$')
        digest = algo.split('_', 1)[1] if '_' in algo else 'sha256'
        dk = hashlib.pbkdf2_hmac(digest, password.encode('utf-8'), bytes.fromhex(salt_hex), int(iters))
        return hmac_compare(dk, bytes.fromhex(hash_hex))
    except Exception:
        return False


def hmac_compare(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


def create_access_token(data: dict) -> str:
    from jose import jwt
    to_encode = dict(data)
    if 'sub' in to_encode and not isinstance(to_encode['sub'], str):
        to_encode['sub'] = str(to_encode['sub'])
    expire = time.time() + ACCESS_TOKEN_EXPIRE_MINUTES * 60
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str):
    from jose import jwt, JWTError
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
