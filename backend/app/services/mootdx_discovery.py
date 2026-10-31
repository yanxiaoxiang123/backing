from __future__ import annotations

import concurrent.futures
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredServer:
    host: str
    port: int
    latency_ms: float
    site: str = ""
    security_count: int = 0


def get_all_candidate_servers() -> list[tuple[str, int, str]]:
    """Aggregate built-in TDX HQ server candidates from tdxpy and mootdx."""
    candidates: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int]] = set()

    raw_hosts: list[tuple[str, str, int] | list] = []
    try:
        from tdxpy.constants import hq_hosts
        raw_hosts.extend(hq_hosts)
    except ImportError:
        logger.debug("tdxpy.constants.hq_hosts unavailable")

    try:
        from mootdx.consts import HQ_HOSTS
        raw_hosts.extend(HQ_HOSTS)
    except ImportError:
        logger.debug("mootdx.consts.HQ_HOSTS unavailable")

    for item in raw_hosts:
        if len(item) >= 3:
            site = str(item[0])
            addr = str(item[1]).strip()
            try:
                port = int(item[2])
            except (ValueError, TypeError):
                continue
            key = (addr, port)
            if key not in seen and addr:
                seen.add(key)
                candidates.append((addr, port, site))

    return candidates


def probe_tdx_server(
    host: str,
    port: int,
    site: str = "",
    timeout_s: float = 1.0,
) -> DiscoveredServer | None:
    """Probe a single TDX server via TdxHq_API, verifying real K-line bars retrieval."""
    try:
        from tdxpy.hq import TdxHq_API

        api = TdxHq_API(heartbeat=False, auto_retry=False, raise_exception=True)
        t0 = time.perf_counter()
        with api.connect(host, port, time_out=timeout_s):
            # Verify actual daily K-line bar retrieval for 000001 (SZ) to ensure full data capability
            bars = api.get_security_bars(9, 0, "000001", 0, 1)
            if bars and len(bars) > 0:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                return DiscoveredServer(
                    host=host,
                    port=port,
                    latency_ms=elapsed_ms,
                    site=site,
                    security_count=len(bars),
                )
    except Exception as exc:
        logger.debug("TDX server %s:%s probe failed: %s", host, port, exc)
    return None


def discover_best_servers(
    limit: int = 5,
    timeout_s: float = 1.0,
    max_workers: int = 30,
    candidates: Iterable[tuple[str, int, str]] | None = None,
) -> list[DiscoveredServer]:
    """Concurrently probe TDX servers and return top candidates sorted by latency."""
    if candidates is None:
        target_candidates = get_all_candidate_servers()
    else:
        target_candidates = list(candidates)

    if not target_candidates:
        logger.warning("No candidate TDX servers found for discovery")
        return []

    logger.info(
        "Probing %d candidate TDX servers (max_workers=%d, timeout=%.1fs)...",
        len(target_candidates),
        max_workers,
        timeout_s,
    )

    results: list[DiscoveredServer] = []

    def _worker(item: tuple[str, int, str]) -> DiscoveredServer | None:
        return probe_tdx_server(item[0], item[1], site=item[2], timeout_s=timeout_s)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_worker, c) for c in target_candidates]
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if res is not None:
                    results.append(res)
            except Exception as exc:
                logger.debug("Discovery probe worker error: %s", exc)

    results.sort(key=lambda s: s.latency_ms)
    selected = results[:limit]
    logger.info(
        "Discovery finished: %d responsive servers found. Selected top %d: %s",
        len(results),
        len(selected),
        [(s.host, s.port, f"{s.latency_ms}ms") for s in selected],
    )
    return selected


def find_env_file(start_path: Path | str | None = None) -> Path:
    """Find the project .env file location."""
    if start_path is not None:
        p = Path(start_path)
        if p.is_dir():
            return p / ".env"
        return p

    # Default lookup: backend/.env or .env in CWD / parent
    cwd = Path.cwd()
    candidates = [
        cwd / ".env",
        cwd / "backend" / ".env",
        cwd.parent / ".env",
        cwd.parent / "backend" / ".env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return (cwd / ".env").resolve()


def update_env_mootdx_servers(
    servers: list[tuple[str, int] | DiscoveredServer],
    env_path: Path | str | None = None,
) -> tuple[Path, str]:
    """Safely update MOOTDX_SERVERS line in the specified .env file."""
    target_path = find_env_file(env_path)

    server_strs: list[str] = []
    for s in servers:
        if isinstance(s, DiscoveredServer):
            server_strs.append(f"{s.host}:{s.port}")
        else:
            server_strs.append(f"{s[0]}:{s[1]}")
    new_value = ",".join(server_strs)
    new_line = f"MOOTDX_SERVERS={new_value}"

    if target_path.is_file():
        content = target_path.read_text(encoding="utf-8")
        pattern = re.compile(r"^MOOTDX_SERVERS=.*$", re.MULTILINE)
        if pattern.search(content):
            new_content = pattern.sub(new_line, content)
        else:
            new_content = content.rstrip() + f"\n\n# mootdx 优选行情服务器 (自动生成)\n{new_line}\n"
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        new_content = f"# mootdx 优选行情服务器 (自动生成)\n{new_line}\n"

    target_path.write_text(new_content, encoding="utf-8")
    logger.info("Updated %s with %s", target_path, new_line)
    return target_path, new_value
