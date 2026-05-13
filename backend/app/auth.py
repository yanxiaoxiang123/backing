# -*- coding: utf-8 -*-
"""API 认证模块"""

import secrets
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings


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
        # If no API key is configured, reject all requests
        raise AuthError("API key not configured on server")

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.API_KEY):
        raise AuthError("Invalid API key")

    return api_key


async def get_current_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    FastAPI 依赖项：获取当前验证的 API 密钥

    Args:
        api_key: 从请求头提取的 API 密钥

    Returns:
        验证通过的 API 密钥
    """
    return validate_api_key(api_key)


def generate_api_key(length: int = 32) -> str:
    """
    生成新的 API 密钥

    Args:
        length: 密钥长度（字节），默认32字节

    Returns:
        新的 API 密钥（十六进制字符串）
    """
    return secrets.token_hex(length)
