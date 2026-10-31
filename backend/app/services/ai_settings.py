"""Persist AI credentials on the server and apply them to subsequent requests."""

import os
import threading

from dotenv import set_key

from app.agent.config import agent_settings
from app.config import BACKEND_DIR, settings
from app.exceptions import AppError, ValidationError

ENV_PATH = BACKEND_DIR / ".env"
_lock = threading.Lock()


def ai_settings_status() -> dict[str, bool]:
    return {"deepseek_configured": bool(settings.DEEPSEEK_API_KEY)}


def update_ai_settings(api_key: object) -> dict[str, bool]:
    if api_key is None:
        return ai_settings_status()
    if not isinstance(api_key, str):
        raise ValidationError("API Key 必须为文本")
    key = api_key.strip()
    if not key:
        return ai_settings_status()
    try:
        key.encode("utf-8")
    except UnicodeError:
        raise ValidationError("API Key 格式无效") from None
    if len(key) > 512 or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in key):
        raise ValidationError("API Key 格式无效，请输入不含空白字符且不超过 512 字符的密钥")

    with _lock:
        try:
            # python-dotenv rewrites atomically, preserving other keys and comments.
            # Existing environment variables must also agree with the saved value
            # for child processes and the TradingAgents bridge.
            set_key(str(ENV_PATH), "DEEPSEEK_API_KEY", key, encoding="utf-8")
        except (OSError, UnicodeError):
            raise AppError("保存 AI 配置失败，请检查服务器配置文件权限") from None
        os.environ["DEEPSEEK_API_KEY"] = key
        settings.DEEPSEEK_API_KEY = key
        agent_settings.DEEPSEEK_API_KEY = key
    return ai_settings_status()
