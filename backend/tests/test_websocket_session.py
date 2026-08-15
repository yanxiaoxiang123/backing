"""WebSocket Session 测试：认证拒绝码、限流码、init/update 消息。

覆盖 realtime 路由的 WS 端点：无需真实行情服务，monkeypatch
``realtime_service.fetch_bars`` 提供固定数据；轮询间隔由
``settings.REALTIME_WS_POLL_S`` 控制以便测试。
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.realtime import router as realtime_router
from app.config import settings
from app.services.realtime_service import STATUS_OK, FetchResult

BAR = {
    "date": "2026-08-14",
    "open": 10.0,
    "high": 10.5,
    "low": 9.8,
    "close": 10.2,
    "volume": 10000,
    "amount": 102000,
    "symbol": "600036",
}


def _ok_result(data=None):
    return FetchResult(status=STATUS_OK, data=list(data) if data is not None else [BAR])


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(realtime_router, prefix="/api/v1", tags=["realtime"])
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _fast_ws_poll():
    original = settings.REALTIME_WS_POLL_S
    settings.REALTIME_WS_POLL_S = 0.05
    yield
    settings.REALTIME_WS_POLL_S = original


@pytest.fixture(autouse=True)
def _clean_tracker():
    from app.api import realtime as realtime_module

    realtime_module._ws_conn_tracker.clear()
    yield
    realtime_module._ws_conn_tracker.clear()


class TestWebSocketAuth:
    def test_missing_api_key_rejected_with_4008(self, client):
        with patch("app.auth.settings") as mock_settings, pytest.raises(
            WebSocketDisconnect
        ) as exc_info:
            mock_settings.API_KEY = "test-secret"
            with client.websocket_connect("/api/v1/ws/realtime/600036"):
                pass
            assert exc_info.value.code == 4008

    def test_invalid_api_key_rejected_with_4008(self, client):
        with patch("app.auth.settings") as mock_settings, pytest.raises(
            WebSocketDisconnect
        ) as exc_info:
            mock_settings.API_KEY = "test-secret"
            with client.websocket_connect(
                "/api/v1/ws/realtime/600036?api_key=wrong"
            ):
                pass
            assert exc_info.value.code == 4008

    def test_valid_api_key_connects_and_receives_init(self, client):
        with patch("app.auth.settings") as mock_settings, patch(
            "app.api.realtime.realtime_service.fetch_bars",
            return_value=_ok_result(),
        ):
            mock_settings.API_KEY = "test-secret"
            with client.websocket_connect(
                "/api/v1/ws/realtime/600036?api_key=test-secret"
            ) as ws:
                message = ws.receive_json()
                assert message["type"] == "init"
                assert message["status"] == "ok"
                assert message["data"][0]["close"] == 10.2

    def test_period_mapping_weekly(self, client):
        with patch("app.auth.settings") as mock_settings, patch(
            "app.api.realtime.realtime_service.fetch_bars",
            return_value=_ok_result(),
        ) as mock_bars:
            mock_settings.API_KEY = "test-secret"
            with client.websocket_connect(
                "/api/v1/ws/realtime/600036?api_key=test-secret&period=weekly"
            ) as ws:
                ws.receive_json()  # init
                # 周K：frequency=5, offset=104
                call = mock_bars.call_args_list[0]
                assert call.args == ("600036", "weekly")


class TestWebSocketRateLimit:
    def test_sixth_connection_rejected_with_4009(self, client):
        with patch("app.auth.settings") as mock_settings, patch(
            "app.api.realtime.realtime_service.fetch_bars",
            return_value=_ok_result(),
        ):
            mock_settings.API_KEY = "test-secret"
            url = "/api/v1/ws/realtime/600036?api_key=test-secret"

            sessions = [client.websocket_connect(url) for _ in range(5)]
            for session in sessions:
                session.__enter__()

            try:
                with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(url):
                    pass
                assert exc_info.value.code == 4009
            finally:
                for session in sessions:
                    session.__exit__(None, None, None)


class TestWebSocketLifecycle:
    def test_cleanup_after_disconnect(self, client):
        from app.api import realtime as realtime_module

        with patch("app.auth.settings") as mock_settings, patch(
            "app.api.realtime.realtime_service.fetch_bars",
            return_value=_ok_result(),
        ):
            mock_settings.API_KEY = "test-secret"
            with client.websocket_connect(
                "/api/v1/ws/realtime/600036?api_key=test-secret"
            ) as ws:
                ws.receive_json()
            # 断开后连接计数应清理
            assert realtime_module._ws_conn_tracker.get("testclient", 0) == 0
