"""Authenticated backend-only Kronos client; never exposes credentials to the UI."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import time

import httpx

from app.config import settings
from app.exceptions import ExternalServiceError, ProviderTimeoutError, ProviderUnavailableError

MODEL_REVISIONS = {
    "kronos-small": "901c26c1332695a2a8f243eb2f37243a37bea320",
    "kronos-base": "2b554741eca47781b64468546e77fef3e85130e6",
}
SOURCE_REVISION = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
TOKENIZER_REVISION = "0e0117387f39004a9016484a186a908917e22426"


class KronosClient:
    def __init__(self):
        if not settings.KRONOS_SERVICE_URL or not settings.KRONOS_SERVICE_TOKEN:
            raise ProviderUnavailableError("远程 Kronos 服务尚未配置", provider="kronos", retryable=False)
        self.base_url = settings.KRONOS_SERVICE_URL.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.KRONOS_SERVICE_TOKEN}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            with httpx.Client(
                base_url=self.base_url, headers=self.headers,
                timeout=httpx.Timeout(5 if path == "/v1/status" else settings.KRONOS_REQUEST_TIMEOUT_S, connect=5),
                trust_env=False,
            ) as client:
                return client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("远程 Kronos 推理超时", provider="kronos") from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError("无法连接远程 Kronos 服务", provider="kronos") from exc

    @staticmethod
    def _error(response: httpx.Response) -> None:
        if response.is_success:
            return
        messages = {
            "gpu_oom": "远程 GPU 显存不足，请释放容量后重试",
            "model_unavailable": "远程固定版本模型或运行依赖不可用",
            "inference_failed": "Kronos 推理失败，未生成替代预测",
            "unauthorized": "远程 Kronos 服务认证失败，请检查后端配置",
        }
        try:
            detail = response.json().get("detail", {})
            code = detail.get("code", "remote_error") if isinstance(detail, dict) else "invalid_input"
        except (ValueError, AttributeError):
            code = "remote_error"
        raise ExternalServiceError(
            detail=messages.get(code, f"远程 Kronos 返回错误（HTTP {response.status_code}）"),
            error_code=code, provider="kronos", retryable=False,
        )

    def status(self) -> dict:
        response = self._request("GET", "/v1/status")
        self._error(response)
        state = response.json()
        models = {row["id"]: row["revision"] for row in state.get("models", [])}
        if (state.get("source_revision") != SOURCE_REVISION
                or state.get("tokenizer_revision") != TOKENIZER_REVISION or models != MODEL_REVISIONS):
            raise ValueError("远程 Kronos 服务版本不匹配")
        return state

    def _predict_with_progress(self, payload: dict, check, progress) -> httpx.Response:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._request, "POST", "/v1/predict", json=payload)
            while True:
                try:
                    return future.result(timeout=1)
                except FutureTimeout:
                    check()
                    try:
                        state = self.status()
                    except (ProviderTimeoutError, ProviderUnavailableError):
                        continue  # A telemetry timeout must not discard an active inference.
                    phase = state.get("phase")
                    if phase == "loading_model":
                        progress("加载模型")
                    elif phase == "inference":
                        progress("推理中")

    def predict(self, payload: dict, check: Callable[[], None],
                progress: Callable[[str], None]) -> dict:
        deadline = time.monotonic() + settings.KRONOS_REQUEST_TIMEOUT_S
        while True:
            check()
            state = self.status()
            if state.get("busy"):
                progress("等待 GPU · " + ("加载模型" if state.get("phase") == "loading_model" else "推理中"))
            else:
                progress("加载模型并推理" if state.get("loaded_model") != payload["model"] else "推理中")
                response = self._predict_with_progress(payload, check, progress)
                if response.status_code != 429:
                    self._error(response)
                    result = response.json()
                    if (result.get("model") != payload["model"]
                            or result.get("model_revision") != MODEL_REVISIONS[payload["model"]]
                            or result.get("source_revision") != SOURCE_REVISION
                            or result.get("tokenizer_revision") != TOKENIZER_REVISION):
                        raise ValueError("远程 Kronos 返回的模型版本与固定版本不一致")
                    check()
                    return result
            if time.monotonic() >= deadline:
                raise ProviderTimeoutError("等待远程 GPU 超时", provider="kronos")
            for _ in range(4):
                check()
                time.sleep(0.5)
