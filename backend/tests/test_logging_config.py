"""结构化日志测试：JSON 输出、脱敏、截断、contextvars 关联。"""

import json
import logging

from app.logging_config import (
    JsonFormatter,
    is_sensitive_key,
    job_id_var,
    redact,
    request_id_var,
)


def _format_record(formatter, message, **extras):
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    return json.loads(formatter.format(record))


class TestJsonFormatter:
    def test_emits_valid_json_with_ts_level_logger_message(self):
        data = _format_record(JsonFormatter(), "hello world")
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["ts"].endswith("Z")

    def test_structured_extras_are_included(self):
        data = _format_record(
            JsonFormatter(),
            "job progress",
            job_id="job-1",
            provider="baostock",
            job_type="sync",
        )
        assert data["job_id"] == "job-1"
        assert data["provider"] == "baostock"
        assert data["job_type"] == "sync"

    def test_request_id_from_contextvar(self):
        formatter = JsonFormatter()
        token = request_id_var.set("req-abc")
        try:
            data = _format_record(formatter, "in request")
        finally:
            request_id_var.reset(token)
        assert data["request_id"] == "req-abc"

    def test_job_id_from_contextvar(self):
        formatter = JsonFormatter()
        token = job_id_var.set("job-xyz")
        try:
            data = _format_record(formatter, "in job")
        finally:
            job_id_var.reset(token)
        assert data["job_id"] == "job-xyz"


class TestRedaction:
    def test_sensitive_keys_masked(self):
        payload = {"api_key": "sk-123", "normal": "value", "nested": {"token": "t"}}
        out = redact(payload)
        assert out["api_key"] == "***"
        assert out["nested"]["token"] == "***"
        assert out["normal"] == "value"

    def test_long_values_truncated(self):
        long_str = "x" * 5000
        assert len(redact(long_str)) < 5000
        assert "[truncated" in redact(long_str)

    def test_is_sensitive_key(self):
        assert is_sensitive_key("API_KEY")
        assert is_sensitive_key("authorization")
        assert is_sensitive_key("password_hash")
        assert not is_sensitive_key("stock_code")

    def test_formatter_redacts_and_whitelists_extras(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            "t", logging.INFO, __file__, 1, "msg", (), None
        )
        record.api_key = "super-secret"  # 非白名单字段直接丢弃（不泄露）
        record.job_type = "sync"  # 白名单字段保留
        data = json.loads(formatter.format(record))
        assert "api_key" not in data
        assert data["job_type"] == "sync"


class TestExceptionFormatting:
    def test_exc_info_serialized_as_string(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                "t", logging.ERROR, __file__, 1, "failed", (), None
            )
            record.exc_info = __import__("sys").exc_info()
        data = json.loads(formatter.format(record))
        assert "exc_info" in data
        assert "ValueError: boom" in data["exc_info"]
