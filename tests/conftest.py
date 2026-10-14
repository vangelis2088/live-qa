import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("TOPICS_FILE", str(tmp_path / "topics.json"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
