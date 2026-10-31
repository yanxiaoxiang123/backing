"""启动时确保配置的登录账号存在。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Base, Settings
from app.models.models import User
from app.passwords import verify_password
from app.services.auth_users import ensure_auth_user, resolve_credentials


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()
    engine.dispose()


class TestEnsureAuthUser:
    def test_creates_missing_user(self, db):
        assert ensure_auth_user(db, username="admin", password="pw-123456") is True
        user = db.query(User).filter(User.username == "admin").one()
        assert verify_password("pw-123456", user.password_hash)

    def test_is_idempotent_when_password_unchanged(self, db):
        ensure_auth_user(db, username="admin", password="pw-123456")
        before = db.query(User).filter(User.username == "admin").one().password_hash
        assert ensure_auth_user(db, username="admin", password="pw-123456") is False
        after = db.query(User).filter(User.username == "admin").one().password_hash
        assert before == after

    def test_rotates_hash_when_password_changes(self, db):
        ensure_auth_user(db, username="admin", password="old-password")
        assert ensure_auth_user(db, username="admin", password="new-password") is True
        user = db.query(User).filter(User.username == "admin").one()
        assert verify_password("new-password", user.password_hash)
        assert not verify_password("old-password", user.password_hash)

    def test_does_nothing_without_password(self, db):
        assert ensure_auth_user(db, username="admin", password=None) is False
        assert db.query(User).count() == 0


class TestResolveCredentials:
    def test_explicit_password_wins(self):
        assert resolve_credentials("analyst", "pw", "api-key") == ("analyst", "pw")

    def test_falls_back_to_api_key(self):
        assert resolve_credentials(None, None, "api-key") == ("admin", "api-key")

    def test_no_password_configured(self):
        assert resolve_credentials("analyst", None, None) == ("analyst", None)

    def test_blank_username_defaults_to_admin(self):
        assert resolve_credentials("   ", "pw", None) == ("admin", "pw")


class TestAuthSettings:
    def test_defaults(self):
        s = Settings(_env_file=None)
        assert s.AUTH_USERNAME == "admin"
        assert s.AUTH_PASSWORD is None
