from pathlib import Path

from dotenv import dotenv_values

from app.runtime_env import backend_env_file


def test_default_environment_file_is_backend_local(monkeypatch):
    monkeypatch.delenv("BACKING_ENV_FILE", raising=False)
    assert backend_env_file() == Path(__file__).resolve().parents[1] / ".env"


def test_external_environment_file_is_the_persistent_write_target(monkeypatch, tmp_path):
    from app.services import ai_settings

    config = tmp_path / "runtime-config" / "backend.env"
    config.parent.mkdir()
    config.write_text("DEEPSEEK_API_KEY='old-test-key'\nAPI_KEY='test-login-key'\n")
    monkeypatch.setenv("BACKING_ENV_FILE", str(config))
    assert backend_env_file() == config
    monkeypatch.setattr(ai_settings, "ENV_PATH", backend_env_file())
    monkeypatch.setattr(ai_settings.settings, "DEEPSEEK_API_KEY", "old-test-key")
    monkeypatch.setattr(ai_settings.agent_settings, "DEEPSEEK_API_KEY", "old-test-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "old-test-key")
    ai_settings.update_ai_settings("new-test-key")
    assert dotenv_values(config)["DEEPSEEK_API_KEY"] == "new-test-key"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    from app.config import Settings
    from app.agent.config import AgentSettings
    assert Settings(_env_file=config).DEEPSEEK_API_KEY == "new-test-key"
    assert AgentSettings(_env_file=config).DEEPSEEK_API_KEY == "new-test-key"


def test_mootdx_discovery_uses_runtime_configuration_unless_overridden(monkeypatch, tmp_path):
    from app.services.mootdx_discovery import find_env_file

    runtime = tmp_path / "runtime" / "backend.env"
    monkeypatch.setenv("BACKING_ENV_FILE", str(runtime))
    assert find_env_file() == runtime
    assert find_env_file(tmp_path) == tmp_path / ".env"
