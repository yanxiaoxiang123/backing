"""Serialize paper-ledger mutations across threads and application processes."""

from contextlib import contextmanager
import os
import threading

from sqlalchemy import text

from app.config import BACKEND_DIR
from app.services.market_data import digest

_lock = threading.RLock()


@contextmanager
def paper_mutation_lock(db):
    with _lock:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            with db.bind.connect() as connection:
                key = int(digest("backing.paper.ledger")[:15], 16)
                if not connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar():
                    raise ValueError("Paper ledger is being updated; retry")
                try:
                    yield
                finally:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            return
        if dialect != "sqlite":
            raise ValueError("Paper ledger locking supports SQLite and PostgreSQL")
        if db.bind.url.database in (None, "", ":memory:"):
            yield
            return
        directory = BACKEND_DIR / "data" / "locks"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ("paper-" + digest(str(db.bind.url)) + ".lock")).open("a+b") as handle:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("Paper ledger is being updated; retry") from exc
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)
