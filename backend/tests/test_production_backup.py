"""Exercise the deployment backup with real SQLite and protected files."""

import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tarfile

import pytest


@pytest.fixture
def operations():
    path = Path(__file__).resolve().parents[2] / "deploy/production/operations.py"
    spec = importlib.util.spec_from_file_location("production_operations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_restore_verification_preserves_live_database_and_configuration(tmp_path, operations):
    for name in ("db", "config", "tls", "backend-data/artifacts"):
        (tmp_path / "shared" / name).mkdir(parents=True)
    (tmp_path / "deployment.env").write_text("BACKING_VERSION=test\n")
    (tmp_path / "shared/config/backend.env").write_text("PRIVATE_KEY=test-only\n")
    (tmp_path / "shared/backend-data/artifacts/result.json").write_text('{"real": true}')
    database = tmp_path / "shared/db/stock_backtest.db"
    with closing(sqlite3.connect(database)) as db:
        db.execute("CREATE TABLE example(id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO example VALUES(1, 'original')")
        db.commit()
    archive = operations.backup(tmp_path)
    with closing(sqlite3.connect(database)) as db:
        db.execute("INSERT INTO example VALUES(2, 'after snapshot')")
        db.commit()
    operations.restore(tmp_path, archive, False)
    assert operations.validate_database(database)["example"] == 2
    with tarfile.open(archive) as snapshot:
        manifest = json.load(snapshot.extractfile("backup-manifest.json"))
        assert manifest["table_counts"]["example"] == 1
        assert "shared/config/backend.env" in manifest["files"]
        assert "shared/backend-data/artifacts/result.json" in manifest["files"]


def test_restore_verification_rejects_tampered_content(tmp_path, operations):
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "changed.txt").write_text("tampered")
    (stage / "backup-manifest.json").write_text(json.dumps({"files": {"changed.txt": "bad"}}))
    (tmp_path / "backups").mkdir()
    archive = tmp_path / "tampered.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(stage / "changed.txt", arcname="changed.txt")
        bundle.add(stage / "backup-manifest.json", arcname="backup-manifest.json")
    with pytest.raises(ValueError, match="checksum"):
        operations.restore(tmp_path, archive, False)


def test_backup_snapshots_live_research_cache_without_copying_wal_files(
    tmp_path, operations, monkeypatch
):
    for name in ("db", "config", "tls", "backend-data"):
        (tmp_path / "shared" / name).mkdir(parents=True)
    database = tmp_path / "shared/db/stock_backtest.db"
    with closing(sqlite3.connect(database)) as db:
        db.execute("CREATE TABLE example(id INTEGER PRIMARY KEY)")
        db.commit()
    cache = tmp_path / "shared/backend-data/research_cache.db"
    with closing(sqlite3.connect(cache)) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("CREATE TABLE research_cache(id INTEGER PRIMARY KEY, payload TEXT)")
        live.executemany(
            "INSERT INTO research_cache VALUES(?, ?)",
            [(index, "evidence" * 100) for index in range(200)],
        )
        live.commit()
        copyfile = operations.shutil.copyfile

        def copy_with_checkpoint(source, target, **kwargs):
            result = copyfile(source, target, **kwargs)
            if Path(source) == cache:
                # A writer can reset the WAL between copytree's independent reads.
                live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                live.execute("INSERT INTO research_cache VALUES(200, 'new evidence')")
                live.commit()
            return result

        monkeypatch.setattr(operations.shutil, "copyfile", copy_with_checkpoint)
        archive = operations.backup(tmp_path)
        restored = tmp_path / "extracted"
        with tarfile.open(archive) as bundle:
            bundle.extractall(restored, filter="data")
            assert not any(
                name.endswith(("research_cache.db-wal", "research_cache.db-shm"))
                for name in bundle.getnames()
            )
        restored_cache = restored / "shared/backend-data/research_cache.db"
        assert operations.validate_database(restored_cache) == {"research_cache": 200}
        operations.restore(tmp_path, archive, False)


def test_restore_verification_rejects_corrupt_research_cache_with_valid_checksum(
    tmp_path, operations
):
    stage = tmp_path / "stage"
    database = stage / "shared/db/stock_backtest.db"
    database.parent.mkdir(parents=True)
    with closing(sqlite3.connect(database)) as db:
        db.execute("CREATE TABLE example(id INTEGER PRIMARY KEY)")
        db.commit()
    cache = stage / "shared/backend-data/research_cache.db"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"damaged sqlite evidence cache")
    manifest = {
        "table_counts": {"example": 0},
        "files": {
            path.relative_to(stage).as_posix(): operations.sha256(path)
            for path in (database, cache)
        },
    }
    (stage / "backup-manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "backups").mkdir()
    archive = tmp_path / "corrupt-cache.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for child in stage.iterdir():
            bundle.add(child, arcname=child.name)

    with pytest.raises((sqlite3.DatabaseError, ValueError)):
        operations.restore(tmp_path, archive, False)
