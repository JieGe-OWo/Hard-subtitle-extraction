from pydantic import BaseModel, EmailStr, field_validator


class SendCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    code: str
    password: str

    @field_validator('code')
    @classmethod
    def _v(cls, v):
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError('验证码格式不正确')
        return v

    @field_validator('password')
    @classmethod
    def _p(cls, v):
        if len(v) < 6 or len(v) > 64:
            raise ValueError('密码长度需在 6-64 位之间')
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ActivateRequest(BaseModel):
    code: str

    @field_validator('code')
    @classmethod
    def _v(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('激活码不能为空')
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class GenerateCodesRequest(BaseModel):
    count: int = 1
    note: str = ''
    expires_in_days: int = 30
    prefix: str = ''


class CustomCodeRequest(BaseModel):
    code: str
    note: str = ''
    expires_in_days: int = 30

    @field_validator('code')
    @classmethod
    def _v(cls, v):
        v = v.strip()
        if len(v) < 4 or len(v) > 64:
            raise ValueError('激活码长度需在 4-64 之间')
        return v


class UpdateUserRequest(BaseModel):
    status: str = ''
    note: str = ''
