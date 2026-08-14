"""领域异常 + 全局 handler 的 API 错误合约测试。

构建一个最小的 FastAPI 应用（仅错误处理器 + 测试路由），断言稳定错误码、
502/503、provider/retryable 字段和 ``raise ... from`` 语义。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.error_handlers import register_error_handlers
from app.exceptions import (
    AppError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ValidationError,
)


@pytest.fixture()
def client():
    app = FastAPI()

    @app.get("/not-found")
    def not_found():
        raise NotFoundError(detail="Job not found")

    @app.get("/validation")
    def validation():
        raise ValidationError(detail="Bad input")

    @app.get("/conflict")
    def conflict():
        raise ConflictError(detail="Already finished")

    @app.get("/bad-gateway")
    def bad_gateway():
        try:
            raise ConnectionError("provider refused")
        except ConnectionError as exc:
            raise ExternalServiceError(
                detail="Stock sync failed", provider="baostock", retryable=True
            ) from exc

    @app.get("/unavailable")
    def unavailable():
        raise ProviderUnavailableError(
            detail="LLM service not available", provider="deepseek"
        )

    @app.get("/timeout")
    def timeout():
        raise ProviderTimeoutError(
            detail="provider timed out", provider="mootdx"
        )

    @app.get("/app-error")
    def app_error():
        raise AppError(detail="Internal boom")

    @app.get("/crash")
    def crash():
        raise RuntimeError("unexpected programming error")

    register_error_handlers(app)
    # raise_server_exceptions=False：让未处理异常以 500 响应返回（同真实客户端）
    return TestClient(app, raise_server_exceptions=False)


class TestErrorContract:
    def test_not_found_shape(self, client):
        resp = client.get("/not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"] == "Job not found"

    def test_validation_shape(self, client):
        resp = client.get("/validation")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation_error"

    def test_conflict_shape(self, client):
        resp = client.get("/conflict")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_external_service_502_with_provider_and_retryable(self, client):
        resp = client.get("/bad-gateway")
        assert resp.status_code == 502
        body = resp.json()["error"]
        assert body["code"] == "external_service_error"
        assert body["provider"] == "baostock"
        assert body["retryable"] is True

    def test_provider_unavailable_503(self, client):
        resp = client.get("/unavailable")
        assert resp.status_code == 503
        body = resp.json()["error"]
        assert body["code"] == "provider_unavailable"
        assert body["provider"] == "deepseek"

    def test_provider_timeout_503(self, client):
        resp = client.get("/timeout")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "provider_timeout"

    def test_generic_app_error_500_stable_code(self, client):
        resp = client.get("/app-error")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "internal_error"

    def test_unhandled_exception_500_stable_code(self, client):
        resp = client.get("/crash")
        assert resp.status_code == 500
        body = resp.json()["error"]
        # 不泄露内部错误信息，只给稳定错误码
        assert body["code"] == "internal_error"
        assert "unexpected" not in body["message"]


class TestExceptionTypes:
    def test_error_codes_are_stable_strings(self):
        assert NotFoundError().error_code == "not_found"
        assert ValidationError().error_code == "validation_error"
        assert ConflictError().error_code == "conflict"
        assert ExternalServiceError().error_code == "external_service_error"
        assert ProviderUnavailableError().error_code == "provider_unavailable"
        assert ProviderTimeoutError().error_code == "provider_timeout"

    def test_provider_errors_are_retryable_by_default(self):
        assert ProviderUnavailableError().retryable is True
        assert ProviderTimeoutError().retryable is True
        assert ExternalServiceError().retryable is False

    def test_app_error_chain_preserved(self):
        try:
            try:
                raise ValueError("root cause")
            except ValueError as exc:
                raise NotFoundError(detail="wrapped") from exc
        except NotFoundError as exc:
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)
