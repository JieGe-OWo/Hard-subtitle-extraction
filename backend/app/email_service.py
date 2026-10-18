import random
import smtplib
import ssl
import time
from email.mime.text import MIMEText

from app.config import (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
                        SMTP_FROM, SMTP_FROM_NAME, SMTP_SSL)


def generate_code(length: int = 6) -> str:
    return ''.join(random.choices('0123456789', k=length))


def send_email(to_email: str, code: str) -> bool:
    """发送邮件。SMTP 未配置时返回 False（开发模式由调用方处理）"""
    if not SMTP_HOST:
        return False
    subject = f'[{SMTP_FROM_NAME}] 您的验证码'
    body = f'您的验证码是：{code}\n\n该验证码 10 分钟内有效。如果不是您本人操作，请忽略此邮件。'
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM or SMTP_USERNAME
    msg['To'] = to_email
    try:
        if SMTP_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(msg['From'], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(msg['From'], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f'[email] 发送失败: {e}')
        return False
