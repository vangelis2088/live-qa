import json

from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_create_topic_returns_partial(client):
    r = client.post("/topics", data={"title": "Rust <b>", "author": "Ann"})
    assert r.status_code == 200
    assert "Rust &lt;b&gt;" in r.text
    assert "Ann" in r.text
    assert "<html" not in r.text
    assert "Organizer's pick" not in r.text


def test_empty_title_rejected(client):
    for title in ["", "   "]:
        r = client.post("/topics", data={"title": title})
        assert r.status_code == 422
        assert "Please enter a topic" in r.text
    assert db.list_topics() == []


def test_title_length_limit(client):
    r = client.post("/topics", data={"title": "x" * 281})
    assert r.status_code == 422
    assert db.list_topics() == []
    r = client.post("/topics", data={"title": "x" * 280})
    assert r.status_code == 200
    assert len(db.list_topics()) == 1


def test_list_newest_first(client):
    client.post("/topics", data={"title": "first"})
    client.post("/topics", data={"title": "second"})
    html = client.get("/topics").text
    assert html.index("second") < html.index("first")


def test_index_has_form_and_polling(client):
    html = client.get("/").text
    assert 'hx-post="/topics"' in html
    assert 'hx-trigger="every 3s"' in html


def test_startup_loads_organizer_topics_once(tmp_path, monkeypatch):
    f = tmp_path / "topics.json"
    f.write_text(json.dumps([{"title": "Keynote ideas"}]))
    monkeypatch.setenv("TOPICS_FILE", str(f))
    for _ in range(2):
        with TestClient(app) as c:
            html = c.get("/").text
    assert html.count("Keynote ideas") == 1
    assert "Organizer's pick" in html
