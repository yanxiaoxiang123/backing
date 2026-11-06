import pytest

from app.api.dl_prediction import _convert_to_baostock_code
from app.services.baostock_service import BaostockService
from app.services.dl_prediction.backtest import DLBacktester
from app.services.dl_prediction.predictor import _next_business_dates


def test_next_business_dates_are_unique_and_skip_weekends():
    assert _next_business_dates("2026-10-30", 5) == [
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
    ]


@pytest.mark.parametrize(
    ("raw_code", "expected_baostock_code", "expected_akshare_symbol"),
    [
        ("600000", "sh.600000", "600000"),
        ("600519", "sh.600519", "600519"),
        ("688001", "sh.688001", "688001"),
        ("000001", "sz.000001", "000001"),
        ("002594", "sz.002594", "002594"),
        ("300750", "sz.300750", "300750"),
        ("sh.600000", "sh.600000", "600000"),
        ("sz.000001", "sz.000001", "000001"),
    ],
)
def test_convert_to_baostock_code_and_downstream_akshare_symbol(
    raw_code: str, expected_baostock_code: str, expected_akshare_symbol: str
):
    # Test API helper
    api_bs_code = _convert_to_baostock_code(raw_code)
    assert api_bs_code == expected_baostock_code

    # Test DLBacktester method
    backtester = DLBacktester()
    backtester_bs_code = backtester._convert_to_baostock_code(raw_code)
    assert backtester_bs_code == expected_baostock_code

    # Verify downstream _to_akshare_symbol in BaostockService extracts the numeric stock code,
    # rather than market prefix/suffix
    bs_service = BaostockService()
    ak_symbol = bs_service._to_akshare_symbol(api_bs_code)
    assert ak_symbol == expected_akshare_symbol


def _build_test_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dl_prediction import router as dl_prediction_router
    from app.auth import get_current_api_key
    from app.error_handlers import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(dl_prediction_router, prefix="/api/v1/dl")
    app.dependency_overrides[get_current_api_key] = lambda: "test-key"
    return TestClient(app)


def test_predict_failure_raises_502_contract():
    from unittest.mock import patch

    client = _build_test_client()
    with patch("app.api.dl_prediction.BaostockService") as mock_bs:
        mock_bs.return_value.get_daily_kline.side_effect = RuntimeError("网络异常")
        resp = client.post("/api/v1/dl/predict", json={"stock_code": "600000"})
        assert resp.status_code == 502
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "prediction_failed"
        assert "网络异常" in body["error"]["message"]


def test_backtest_failure_raises_502_contract():
    from unittest.mock import patch

    client = _build_test_client()
    with patch("app.api.dl_prediction.DLBacktester") as mock_bt:
        mock_bt.return_value.run_backtest.side_effect = RuntimeError("计算错误")
        resp = client.post(
            "/api/v1/dl/backtest",
            json={
                "stock_code": "600000",
                "start_date": "2024-01-01",
                "end_date": "2024-06-01",
            },
        )
        assert resp.status_code == 502
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "backtest_failed"
        assert "计算错误" in body["error"]["message"]


def test_predict_empty_data_returns_404():
    from unittest.mock import patch

    client = _build_test_client()
    with patch("app.api.dl_prediction.BaostockService") as mock_bs:
        mock_bs.return_value.get_daily_kline.return_value = None
        resp = client.post("/api/v1/dl/predict", json={"stock_code": "600000"})
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "not_found"


def test_external_service_error_constructor():
    from app.exceptions import ExternalServiceError

    err1 = ExternalServiceError("prediction_failed", "detail message")
    assert err1.error_code == "prediction_failed"
    assert err1.detail == "detail message"

    err2 = ExternalServiceError(detail="detail msg", provider="baostock")
    assert err2.error_code == "external_service_error"
    assert err2.detail == "detail msg"
    assert err2.provider == "baostock"

