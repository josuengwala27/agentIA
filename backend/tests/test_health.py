import os

import pytest
from fastapi.testclient import TestClient


# Permet d'exécuter les tests sans exiger Postgres au démarrage de FastAPI.
os.environ.setdefault("SKIP_DB_INIT", "1")

from app.main import app  # noqa: E402


client = TestClient(app)


def test_api_health() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_api_root() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "message" in res.json()

