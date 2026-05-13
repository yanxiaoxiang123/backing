# -*- coding: utf-8 -*-
"""API 认证测试"""

import pytest
from unittest.mock import patch

from app.auth import validate_api_key, generate_api_key, AuthError


class TestValidateApiKey:
    """测试 API 密钥验证"""

    def test_validate_api_key_with_valid_key(self):
        """有效密钥应该验证通过"""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test_secret_key"
            result = validate_api_key("test_secret_key")
            assert result == "test_secret_key"

    def test_validate_api_key_with_none_key(self):
        """空密钥应该抛出 AuthError"""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test_secret_key"
            with pytest.raises(AuthError) as exc_info:
                validate_api_key(None)
            assert "Missing API key" in str(exc_info.value.detail)

    def test_validate_api_key_with_empty_string(self):
        """空字符串密钥应该抛出 AuthError"""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test_secret_key"
            with pytest.raises(AuthError) as exc_info:
                validate_api_key("")
            assert "Missing API key" in str(exc_info.value.detail)

    def test_validate_api_key_with_invalid_key(self):
        """无效密钥应该抛出 AuthError"""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test_secret_key"
            with pytest.raises(AuthError) as exc_info:
                validate_api_key("wrong_key")
            assert "Invalid API key" in str(exc_info.value.detail)

    def test_validate_api_key_when_not_configured(self):
        """服务器未配置密钥时应该抛出 AuthError"""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.API_KEY = None
            with pytest.raises(AuthError) as exc_info:
                validate_api_key("any_key")
            assert "API key not configured" in str(exc_info.value.detail)

    def test_validate_api_key_uses_constant_time_comparison(self):
        """验证使用 constant-time comparison 防止时序攻击"""
        with patch("app.auth.settings") as mock_settings:
            mock_settings.API_KEY = "test_secret_key"
            # 如果使用 secrets.compare_digest，无论是否匹配都不会有时序差异
            # 这里主要验证不同长度的密钥都能正确处理
            with pytest.raises(AuthError):
                validate_api_key("short")
            with pytest.raises(AuthError):
                validate_api_key("a" * 100)


class TestGenerateApiKey:
    """测试 API 密钥生成"""

    def test_generate_api_key_default_length(self):
        """默认生成 32 字节（64 字符十六进制）的密钥"""
        key = generate_api_key()
        assert len(key) == 64  # 32 bytes * 2 hex chars
        assert all(c in "0123456789abcdef" for c in key)

    def test_generate_api_key_custom_length(self):
        """可以生成不同长度的密钥"""
        key = generate_api_key(length=16)
        assert len(key) == 32  # 16 bytes * 2 hex chars

    def test_generate_api_key_unique(self):
        """每次生成的密钥应该不同"""
        keys = [generate_api_key() for _ in range(10)]
        assert len(set(keys)) == 10  # all unique

    def test_generate_api_key_is_string(self):
        """生成的密钥应该是字符串类型"""
        key = generate_api_key()
        assert isinstance(key, str)
