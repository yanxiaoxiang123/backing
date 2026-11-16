"""Private online backups and offline restore for this Compose deployment."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def validate_database(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Database foreign key check failed")
        return {
            name: db.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0]
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def snapshot_database(source: Path, target: Path) -> dict[str, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(target)) as snapshot:
            original.backup(snapshot)
            snapshot.execute("PRAGMA journal_mode=DELETE")
    return validate_database(target)


def backup(root: Path) -> Path:
    directory = root / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".backup-", dir=directory) as temporary:
        stage = Path(temporary)
        database = stage / "shared/db/stock_backtest.db"
        source = root / "shared/db/stock_backtest.db"
        counts = snapshot_database(source, database)
        for name in ("config", "tls", "backend-data"):
            ignore = (
                shutil.ignore_patterns(
                    "research_cache.db", "research_cache.db-wal", "research_cache.db-shm"
                ) if name == "backend-data" else None
            )
            shutil.copytree(root / "shared" / name, stage / "shared" / name, ignore=ignore)
        cache_source = root / "shared/backend-data/research_cache.db"
        cache_counts = None
        if cache_source.exists():
            cache_counts = snapshot_database(
                cache_source, stage / "shared/backend-data/research_cache.db"
            )
        for name in ("deployment.env", "release.json"):
            if (root / name).exists():
                shutil.copy2(root / name, stage / name)
        now = datetime.now(timezone.utc)
        manifest = {
            "created_at": now.isoformat(), "table_counts": counts,
            "research_cache_table_counts": cache_counts,
            "files": {
                p.relative_to(stage).as_posix(): sha256(p)
                for p in stage.rglob("*") if p.is_file()
            },
        }
        (stage / "backup-manifest.json").write_text(json.dumps(manifest, indent=2))
        result = directory / (now.strftime("backing-%Y%m%dT%H%M%S%fZ") + ".tar.gz")
        partial = result.with_suffix(".partial")
        with tarfile.open(partial, "w:gz") as archive:
            for child in stage.iterdir():
                archive.add(child, arcname=child.name)
        partial.chmod(0o600)
        partial.replace(result)
    # Keep the newest 14 calendar days, including manual safety backups.
    cutoff = now.timestamp() - 14 * 86400
    for old in directory.glob("backing-*.tar.gz"):
        if old.stat().st_mtime < cutoff:
            old.unlink()
    print(json.dumps({"backup": str(result), "tables": len(counts), "integrity": "ok"}))
    return result


def restore(root: Path, archive_path: Path, apply: bool) -> None:
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=root / "backups") as temporary:
        stage = Path(temporary)
        with tarfile.open(archive_path) as archive:
            archive.extractall(stage, filter="data")
        manifest = json.loads((stage / "backup-manifest.json").read_text())
        for name, expected in manifest["files"].items():
            path = (stage / name).resolve()
            if not path.is_relative_to(stage) or sha256(path) != expected:
                raise ValueError("Backup checksum mismatch")
        counts = validate_database(stage / "shared/db/stock_backtest.db")
        if counts != manifest["table_counts"]:
            raise ValueError("Backup table count mismatch")
        cache = stage / "shared/backend-data/research_cache.db"
        if cache.exists():
            cache_counts = validate_database(cache)
            expected_cache_counts = manifest.get("research_cache_table_counts")
            if expected_cache_counts is not None and cache_counts != expected_cache_counts:
                raise ValueError("Research cache table count mismatch")
        if apply:
            backup(root)
            command = ["docker", "compose", "--env-file", str(root / "deployment.env"),
                       "-f", str(root / "source/deploy/production/compose.yaml")]
            subprocess.run(command + ["stop"], check=True)
            for name in ("db", "config", "tls", "backend-data"):
                target = (root / "shared" / name).resolve()
                if target.parent != root / "shared":
                    raise ValueError("Unexpected restore target")
                shutil.rmtree(target)
                shutil.copytree(stage / "shared" / name, target)
            subprocess.run(command + ["up", "-d", "--force-recreate"], check=True)
        print(json.dumps({"restored": apply, "verified": True, "tables": len(counts),
                          "files": len(manifest["files"])}))


def main() -> None:
    import os
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "verify", "restore"])
    parser.add_argument("--root", type=Path, default=Path("/home/yanxx/backing"))
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "deployment.env").is_file():
        parser.error("Not a prepared deployment directory")
    if args.action == "backup":
        backup(root)
    else:
        if not args.archive or (args.action == "restore" and not args.confirm_restore):
            parser.error("Specify --archive; restore also requires --confirm-restore")
        restore(root, args.archive.resolve(), args.action == "restore")


if __name__ == "__main__":
    main()
