# -*- coding: utf-8 -*-
"""启动时确保配置的登录账号存在。

登录账号由 ``AUTH_USERNAME`` / ``AUTH_PASSWORD`` 配置；未配置密码时回退到
``API_KEY``，这样已有部署升级后仍能用原来的密钥登录。两者都没有时不创建
账号（服务器会在启动日志中给出警告）。
"""

import logging

from sqlalchemy.orm import Session

from app.models.models import User
from app.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)

DEFAULT_USERNAME = "admin"


def resolve_credentials(
    auth_username: str | None,
    auth_password: str | None,
    api_key: str | None,
) -> tuple[str, str | None]:
    """Return the configured ``(username, password)`` pair.

    ``AUTH_PASSWORD`` wins; ``API_KEY`` is the upgrade-compatible fallback.
    """
    username = (auth_username or "").strip() or DEFAULT_USERNAME
    password = auth_password or api_key or None
    return username, password


def ensure_auth_user(db: Session, *, username: str, password: str | None) -> bool:
    """Create or update the login account.

    Returns ``True`` when the users table was written. Re-hashing only happens
    when the configured password no longer matches, so repeated startups stay
    cheap and the stored hash is never rewritten needlessly.
    """
    if not password:
        return False

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        db.add(User(username=username, password_hash=hash_password(password)))
        db.commit()
        logger.info("auth user created: %s", username)
        return True

    if not verify_password(password, user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
        logger.info("auth user password rotated: %s", username)
        return True

    return False
