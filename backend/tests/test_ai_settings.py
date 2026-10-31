"""AI key settings must persist without disclosing credentials."""

import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.agent.config import AgentSettings, agent_settings
from app.agent.llm_adapter import LLMToolAdapter
from app.agent_chat.runtime import NativeAgentChatRuntime
from app.api.ai_settings import router as ai_router
from app.api.auth import router as auth_router
from app.config import Base, Settings, get_db, settings
from app.error_handlers import register_error_handlers
from app.limiter import limiter
from app.middleware import CsrfMiddleware

URL = "/api/v1/settings/ai"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # This route contract must never run main.lifespan: its credential bootstrap,
    # job recovery and paper worker otherwise mutate the developer's database.
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="settings-test-session")
    app.add_middleware(CsrfMiddleware)
    app.include_router(ai_router)
    app.include_router(auth_router)
    app.state.limiter = limiter
    register_error_handlers(app)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def isolated_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "API_KEY", "login-secret")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "old-ai-key")
    monkeypatch.setattr(agent_settings, "DEEPSEEK_API_KEY", "old-ai-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "old-ai-key")
    # Patch the storage location, never the user's actual .env.
    import app.services.ai_settings as service

    monkeypatch.setattr(service, "ENV_PATH", tmp_path / ".env")
    (tmp_path / ".env").write_text(
        "# existing configuration\nAPI_KEY='login-secret'\n"
        "DEEPSEEK_API_KEY='old-ai-key'\nTAVILY_API_KEY='search-key'\n",
        encoding="utf-8",
    )
    with TestClient(app, raise_server_exceptions=False) as value:
        yield value
    engine.dispose()
    limiter.reset()


def auth_headers():
    return {"X-API-Key": "login-secret"}


def test_settings_require_authentication(client):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"deepseek_api_key": "new-key"}).status_code == 401


def test_status_never_discloses_key(client):
    response = client.get(URL, headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == {"deepseek_configured": True}
    assert "old-ai-key" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_save_updates_legacy_chat_and_restart_configuration(client, tmp_path, monkeypatch):
    runtime = NativeAgentChatRuntime(
        lambda: None, api_key_provider=lambda: settings.DEEPSEEK_API_KEY
    )
    response = client.put(
        URL, headers=auth_headers(), json={"deepseek_api_key": "new-ai-key"}
    )
    assert response.status_code == 200
    assert response.json() == {"deepseek_configured": True}
    assert "new-ai-key" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert LLMToolAdapter().api_key == "new-ai-key"
    assert runtime.status["available"] is True
    # Environment and settings readers used by the TA bridge must agree.
    assert settings.DEEPSEEK_API_KEY == "new-ai-key"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert Settings(_env_file=tmp_path / ".env").DEEPSEEK_API_KEY == "new-ai-key"
    assert AgentSettings(_env_file=tmp_path / ".env").DEEPSEEK_API_KEY == "new-ai-key"
    values = dotenv_values(tmp_path / ".env")
    assert values["DEEPSEEK_API_KEY"] == "new-ai-key"
    assert values["API_KEY"] == "login-secret"
    assert values["TAVILY_API_KEY"] == "search-key"
    assert "# existing configuration" in (tmp_path / ".env").read_text()


@pytest.mark.parametrize("key", [None, "", "   "])
def test_empty_input_preserves_existing_key(client, tmp_path, key):
    before = (tmp_path / ".env").read_bytes()
    response = client.put(URL, headers=auth_headers(), json={"deepseek_api_key": key})
    assert response.status_code == 200
    assert response.json() == {"deepseek_configured": True}
    assert (tmp_path / ".env").read_bytes() == before
    assert settings.DEEPSEEK_API_KEY == "old-ai-key"


@pytest.mark.parametrize("key", [123, {"secret": "sensitive"}, "key\nBAD=value", "x" * 513, "key\ud800"])
def test_bad_input_is_rejected_without_echoing_it(client, tmp_path, key):
    before = (tmp_path / ".env").read_bytes()
    response = client.put(URL, headers=auth_headers(), json={"deepseek_api_key": key})
    assert response.status_code == 400
    assert "sensitive" not in response.text
    assert "BAD=value" not in response.text
    assert "x" * 513 not in response.text
    assert (tmp_path / ".env").read_bytes() == before


def test_invalid_json_has_generic_error(client):
    response = client.put(URL, headers=auth_headers(), content="{secret:not-json")
    assert response.status_code == 400
    assert "secret:not-json" not in response.text


def test_write_failure_keeps_active_key(client, monkeypatch):
    import app.services.ai_settings as service

    def fail(*args, **kwargs):
        raise OSError("file unavailable")

    monkeypatch.setattr(service, "set_key", fail)
    response = client.put(
        URL, headers=auth_headers(), json={"deepseek_api_key": "new-ai-key"}
    )
    assert response.status_code == 500
    assert "new-ai-key" not in response.text
    assert settings.DEEPSEEK_API_KEY == "old-ai-key"
    assert LLMToolAdapter().api_key == "old-ai-key"


def test_cookie_auth_requires_csrf_to_save(client):
    login = client.post("/api/v1/auth/session", json={"api_key": "login-secret"})
    assert login.status_code == 200
    assert client.put(URL, json={"deepseek_api_key": "new-ai-key"}).status_code == 403
    response = client.put(
        URL,
        headers={"X-CSRF-Token": login.cookies["csrf_token"]},
        json={"deepseek_api_key": "new-ai-key"},
    )
    assert response.status_code == 200


def test_chat_turn_uses_updated_key_without_restarting(client, monkeypatch):
    import app.agent_chat.runtime as native

    used_keys = []

    class Model:
        def __init__(self, *, api_key, **kwargs):
            used_keys.append(api_key)

        def complete(self, *args, **kwargs):
            return native.NativeModelResponse(text="hello")

    monkeypatch.setattr(native, "LangChainDeepSeekModel", Model)
    runtime = NativeAgentChatRuntime(
        lambda: None, api_key_provider=lambda: settings.DEEPSEEK_API_KEY
    )
    monkeypatch.setattr(runtime, "_history", lambda *args: ([], ""))
    response = client.put(
        URL, headers=auth_headers(), json={"deepseek_api_key": "rotated-ai-key"}
    )
    assert response.status_code == 200
    outcome = runtime.run_turn("thread", "你好", turn_id=1, emit=lambda _: None)
    assert outcome.status == "completed"
    assert used_keys == ["rotated-ai-key"]
