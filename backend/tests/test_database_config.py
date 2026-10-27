import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import database_url
from app.main import app


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("DATABASE_URL", "PGHOST", "PGPORT", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "value", ["", "sqlite:///ignored", "invalid secret-value", "postgresql://"]
)
def test_invalid_configuration_is_sanitized(monkeypatch, value):
    monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(ValueError, match="Configure a valid PostgreSQL") as error:
        database_url()
    assert "secret-value" not in str(error.value)


def test_compose_password_special_characters_are_preserved(monkeypatch):
    monkeypatch.setenv("PGHOST", "db")
    monkeypatch.setenv("POSTGRES_PASSWORD", "synthetic:@/%password")
    assert database_url().password == "synthetic:@/%password"


def test_readiness_does_not_leak_driver_details(monkeypatch):
    def unavailable():
        raise OperationalError("SELECT secret", {}, Exception("synthetic-secret-value"))

    monkeypatch.setattr("app.main.get_engine", unavailable)
    with TestClient(app) as client:
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database is not ready"}
        assert client.get("/api/health").status_code == 200


def test_readiness_without_configuration(monkeypatch):
    from app.db.session import get_engine

    get_engine.cache_clear()
    with TestClient(app) as client:
        assert client.get("/api/ready").status_code == 503
