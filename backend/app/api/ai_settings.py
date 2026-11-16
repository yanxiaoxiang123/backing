"""Authenticated AI configuration endpoints; credentials are never returned."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from starlette.concurrency import run_in_threadpool

from app.auth import get_current_api_key
from app.exceptions import ValidationError
from app.services.ai_settings import ai_settings_status, update_ai_settings

router = APIRouter(
    prefix="/api/v1/settings/ai",
    tags=["settings"],
    dependencies=[Depends(get_current_api_key)],
)


@router.get("")
def get_ai_settings() -> JSONResponse:
    return JSONResponse(ai_settings_status(), headers={"Cache-Control": "no-store"})


@router.put("")
async def save_ai_settings(request: Request) -> JSONResponse:
    # Parse manually so validation responses cannot echo secret inputs.
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("AI 配置请求格式无效") from None
    if not isinstance(body, dict) or set(body) - {"deepseek_api_key"}:
        raise ValidationError("AI 配置请求字段无效")
    status = await run_in_threadpool(update_ai_settings, body.get("deepseek_api_key"))
    return JSONResponse(status, headers={"Cache-Control": "no-store"})
