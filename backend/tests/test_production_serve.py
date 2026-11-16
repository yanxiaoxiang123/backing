"""The container entry script must find the API when started from /app/serve.py."""

import asyncio
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys

import uvicorn
from uvicorn.importer import import_from_string
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request


def test_entry_script_loads_backend_after_migration_from_outside_module_directory(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "deploy/production/serve.py"
    entry = tmp_path / "app/serve.py"
    backend = entry.parent / "backend"
    backend.mkdir(parents=True)
    (backend / "main.py").write_text("app = 'isolated-api-entry'\n")
    shutil.copy2(source, entry)
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "main", raising=False)
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))

    def serve(target, **kwargs):
        assert calls[0][0][-3:] == ["alembic", "upgrade", "head"]
        assert import_from_string(target) == "isolated-api-entry"
        assert kwargs["workers"] == 1
        assert kwargs["proxy_headers"] is True

    monkeypatch.setattr(uvicorn, "run", serve)
    runpy.run_path(str(entry), run_name="__main__")
    sys.modules.pop("main", None)


def test_spawned_data_worker_does_not_repeat_migrations_or_start_api(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "deploy/production/serve.py"

    def unexpected(*args, **kwargs):
        raise AssertionError("Worker must not rerun the server entry point")

    monkeypatch.setattr(subprocess, "run", unexpected)
    monkeypatch.setattr(uvicorn, "run", unexpected)
    runpy.run_path(str(source), run_name="__mp_main__")


def test_public_proxy_cannot_change_limiter_identity_with_forwarded_headers(monkeypatch):
    deployment = Path(__file__).resolve().parents[2] / "deploy/production"
    server_options = {}
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: server_options.update(kwargs))
    monkeypatch.setattr(sys, "path", list(sys.path))
    runpy.run_path(str(deployment / "serve.py"), run_name="__main__")
    config = (deployment / "nginx.conf").read_text()
    directive = re.search(
        r"^\s*proxy_set_header\s+X-Forwarded-For\s+([^;]+);", config, re.MULTILINE
    ).group(1)
    remote_address = "203.0.113.25"
    identities = []

    async def endpoint(scope, receive, send):
        identities.append(get_remote_address(Request(scope)))
        assert scope["scheme"] == "https"

    proxy = ProxyHeadersMiddleware(
        endpoint, trusted_hosts=server_options["forwarded_allow_ips"]
    )
    for forged_address in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
        # Expand the two documented Nginx variables using a public connection
        # and an attacker-supplied incoming header, then use real ASGI parsing.
        forwarded = directive.replace(
            "$proxy_add_x_forwarded_for", f"{forged_address}, {remote_address}"
        ).replace("$remote_addr", remote_address)
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("172.20.0.2", 12345),
            "headers": [
                (b"x-forwarded-for", forwarded.encode()),
                (b"x-forwarded-proto", b"https"),
            ],
        }
        asyncio.run(proxy(scope, None, None))

    assert identities == [remote_address] * 3
