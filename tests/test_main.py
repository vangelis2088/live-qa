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


def _voter(client):
    return client.cookies.get("voter_id")


def _counts(voter_id=None):
    return {t["title"]: t["votes"] for t in db.list_topics(voter_id)}


def _seed(client, *titles):
    for t in titles:
        client.post("/topics", data={"title": t})


def test_first_vote(client):
    _seed(client, "a")
    topic_id = db.list_topics()[0]["id"]
    r = client.post(f"/topics/{topic_id}/vote")
    assert r.status_code == 200
    assert _voter(client)
    assert _counts() == {"a": 1}
    assert 'class="voted"' in r.text


def test_vote_moves_to_other_topic(client):
    _seed(client, "a", "b")
    ids = {t["title"]: t["id"] for t in db.list_topics()}
    client.post(f"/topics/{ids['a']}/vote")
    client.post(f"/topics/{ids['b']}/vote")
    assert _counts() == {"a": 0, "b": 1}


def test_repeat_vote_does_nothing(client):
    _seed(client, "a")
    topic_id = db.list_topics()[0]["id"]
    for _ in range(3):
        assert client.post(f"/topics/{topic_id}/vote").status_code == 200
    assert _counts() == {"a": 1}


def test_vote_unknown_topic_is_404(client):
    assert client.post("/topics/999/vote").status_code == 404
    assert client.post("/topics/abc/vote").status_code == 422


def test_votes_sorted_desc_then_newest(client):
    _seed(client, "old", "mid", "new")
    ids = {t["title"]: t["id"] for t in db.list_topics()}
    client.post(f"/topics/{ids['mid']}/vote")
    assert [t["title"] for t in db.list_topics()] == ["mid", "new", "old"]


def test_each_browser_has_own_vote_and_forged_cookie_is_replaced(client):
    _seed(client, "a")
    topic_id = db.list_topics()[0]["id"]
    client.post(f"/topics/{topic_id}/vote")
    client.cookies.clear()
    client.cookies.set("voter_id", "not-a-valid-id")
    client.post(f"/topics/{topic_id}/vote")
    assert _counts() == {"a": 2}
