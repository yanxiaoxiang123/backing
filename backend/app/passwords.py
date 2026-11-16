# -*- coding: utf-8 -*-
"""密码哈希：PBKDF2-HMAC-SHA256 + 每用户随机盐。

不引入额外依赖（bcrypt/argon2），标准库即可满足单账号演示系统的需求。
存储格式：``pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>``。
"""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16

# 用户不存在时也跑一次 KDF，避免用响应时间枚举账号。
DUMMY_HASH = (
    f"{ALGORITHM}${ITERATIONS}$"
    f"{'00' * SALT_BYTES}$"
    f"{'00' * 32}"
)


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    """Return a salted PBKDF2 hash for ``password``."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of ``password`` against a stored hash.

    Malformed or empty hashes always return ``False`` instead of raising.
    """
    if not stored:
        return False
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
