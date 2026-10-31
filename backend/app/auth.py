# -*- coding: utf-8 -*-
"""API 认证模块"""

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import User
from app.passwords import DUMMY_HASH, verify_password

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthError(HTTPException):
    """认证错误"""

    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "API-Key"},
        )


def validate_api_key(api_key: Optional[str]) -> str:
    """
    验证 API 密钥

    Args:
        api_key: API 密钥字符串

    Returns:
        验证通过的 API 密钥

    Raises:
        AuthError: 认证失败
    """
    if not api_key:
        raise AuthError("Missing API key - provide X-API-Key header")

    if not settings.API_KEY:
        raise AuthError("API key not configured on server")

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.API_KEY):
        raise AuthError("Invalid API key")

    return api_key


def authenticate_user(db: Session, username: str, password: str) -> User:
    """
    校验账号密码。

    用户不存在时仍执行一次 KDF（DUMMY_HASH），避免通过响应时间枚举账号；
    两种失败返回同一条错误信息。
    """
    user = db.query(User).filter(User.username == username).first()
    stored = user.password_hash if user is not None else DUMMY_HASH
    valid = verify_password(password, stored)
    if user is None or not valid:
        raise AuthError("Invalid username or password")
    return user


async def get_current_api_key(
    api_key: Optional[str] = Security(api_key_header),
    request: Request = None,
) -> str:
    """
    FastAPI 依赖项：获取当前已验证的用户身份。

    认证方式（按优先级）：
    1. HTTP-only session cookie（前端浏览器使用，API key 不暴露在 JS bundle 中）
    2. X-API-Key 请求头（外部 API 客户端使用）

    session 认证返回登录时的用户名；旧会话（无 username）返回 session_user。
    """
    # 优先检查 session cookie（前端浏览器请求）
    if request is not None and request.session.get("authenticated"):
        return request.session.get("username") or "session_user"

    # 回退到 X-API-Key 请求头（外部客户端 / curl）
    return validate_api_key(api_key)


async def get_authenticated_actor(principal: str = Depends(get_current_api_key)) -> str:
    """An audit label must never contain the API-key credential itself."""
    if settings.API_KEY and secrets.compare_digest(principal, settings.API_KEY):
        return "api_key"
    return principal


def generate_api_key(length: int = 32) -> str:
    """
    生成新的 API 密钥

    Args:
        length: 密钥长度（字节），默认32字节

    Returns:
        新的 API 密钥（十六进制字符串）
    """
    return secrets.token_hex(length)
