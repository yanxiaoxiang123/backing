from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import maintenance
from app.services.mootdx_discovery import (
    DiscoveredServer,
    discover_best_servers,
    get_all_candidate_servers,
    probe_tdx_server,
    update_env_mootdx_servers,
)


def test_get_all_candidate_servers():
    candidates = get_all_candidate_servers()
    assert len(candidates) > 20
    assert all(len(c) == 3 for c in candidates)
    # Check deduplication
    keys = [(c[0], c[1]) for c in candidates]
    assert len(keys) == len(set(keys))


def test_probe_tdx_server_success():
    mock_api = MagicMock()
    mock_api.connect.return_value.__enter__.return_value = None
    mock_api.get_security_bars.return_value = [{"close": 10.0}]

    with patch("tdxpy.hq.TdxHq_API", return_value=mock_api):
        res = probe_tdx_server("1.1.1.1", 7709, site="test", timeout_s=0.5)

    assert res is not None
    assert res.host == "1.1.1.1"
    assert res.port == 7709
    assert res.security_count == 1
    assert res.latency_ms >= 0


def test_probe_tdx_server_failure():
    mock_api = MagicMock()
    mock_api.connect.side_effect = TimeoutError("mock timeout")

    with patch("tdxpy.hq.TdxHq_API", return_value=mock_api):
        res = probe_tdx_server("1.1.1.1", 7709, site="test", timeout_s=0.5)

    assert res is None


def test_discover_best_servers_sorting_and_limiting():
    servers = [
        ("1.1.1.1", 7709, "s1"),
        ("2.2.2.2", 7709, "s2"),
        ("3.3.3.3", 7709, "s3"),
    ]

    mock_probed = {
        ("1.1.1.1", 7709): DiscoveredServer("1.1.1.1", 7709, 150.0, "s1", 20000),
        ("2.2.2.2", 7709): DiscoveredServer("2.2.2.2", 7709, 45.0, "s2", 20000),
        ("3.3.3.3", 7709): DiscoveredServer("3.3.3.3", 7709, 90.0, "s3", 20000),
    }

    def _mock_probe(host, port, site="", timeout_s=1.0):
        return mock_probed.get((host, port))

    with patch("app.services.mootdx_discovery.probe_tdx_server", side_effect=_mock_probe):
        best = discover_best_servers(limit=2, candidates=servers)

    assert len(best) == 2
    assert best[0].host == "2.2.2.2"
    assert best[0].latency_ms == 45.0
    assert best[1].host == "3.3.3.3"
    assert best[1].latency_ms == 90.0


def test_update_env_mootdx_servers_updates_existing_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=sqlite:///./test.db\n"
        "MOOTDX_SERVERS=old.ip.1:7709,old.ip.2:7709\n"
        "APP_ENV=development\n",
        encoding="utf-8",
    )

    servers = [
        DiscoveredServer("10.1.1.1", 7709, 50.0),
        DiscoveredServer("10.1.1.2", 80, 60.0),
    ]

    path, val = update_env_mootdx_servers(servers, env_path=env_file)
    assert path == env_file
    assert val == "10.1.1.1:7709,10.1.1.2:80"

    content = env_file.read_text(encoding="utf-8")
    assert "MOOTDX_SERVERS=10.1.1.1:7709,10.1.1.2:80" in content
    assert "DATABASE_URL=sqlite:///./test.db" in content
    assert "APP_ENV=development" in content
    assert "old.ip.1" not in content


def test_update_env_mootdx_servers_creates_new_env_if_missing(tmp_path):
    env_file = tmp_path / "sub" / ".env"
    servers = [("10.2.2.2", 7709)]

    path, val = update_env_mootdx_servers(servers, env_path=env_file)
    assert path.is_file()
    assert val == "10.2.2.2:7709"
    content = env_file.read_text(encoding="utf-8")
    assert "MOOTDX_SERVERS=10.2.2.2:7709" in content


def test_maintenance_update_mootdx_servers_dry_run():
    mock_servers = [
        DiscoveredServer("10.3.3.3", 7709, 30.0, site="mock", security_count=24000)
    ]
    with patch("app.services.mootdx_discovery.discover_best_servers", return_value=mock_servers):
        res = maintenance.update_mootdx_servers(dry_run=True)

    assert res["discovered_count"] == 1
    assert res["dry_run"] is True
    assert "env_file" not in res
    assert res["servers"][0]["host"] == "10.3.3.3"
