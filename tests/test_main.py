import pytest
from markupsafe import escape

from app import db


def test_index_renders_form_and_polling_list(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'hx-post="/questions"' in r.text
    assert 'hx-trigger="every 3s"' in r.text
    assert "No questions yet" in r.text


def test_create_question_returns_partial(client):
    r = client.post("/questions", data={"text": "What is htmx?", "author": "Ada"})
    assert r.status_code == 200
    assert "What is htmx?" in r.text
    assert "Ada" in r.text
    assert "<html" not in r.text
    assert len(db.list_questions()) == 1


def test_create_question_anonymous(client):
    r = client.post("/questions", data={"text": "Anyone?"})
    assert r.status_code == 200
    assert "Anonymous" in r.text
    assert db.list_questions()[0]["author"] is None


def test_questions_partial_lists_existing(client):
    db.create_question("First", None)
    r = client.get("/questions")
    assert r.status_code == 200
    assert "First" in r.text
    assert "<html" not in r.text


@pytest.mark.parametrize("text", ["", "   ", "x" * 281])
def test_create_question_rejects_invalid_text(client, text):
    r = client.post("/questions", data={"text": text})
    assert r.status_code == 422
    assert db.list_questions() == []


def test_create_question_accepts_max_length(client):
    r = client.post("/questions", data={"text": "x" * 280})
    assert r.status_code == 200
    assert len(db.list_questions()) == 1


def test_create_question_rejects_long_author(client):
    r = client.post("/questions", data={"text": "Hi", "author": "a" * 51})
    assert r.status_code == 422
    assert db.list_questions() == []


def test_question_text_is_escaped(client):
    r = client.post("/questions", data={"text": "<script>alert(1)</script>"})
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_upvote_increments_and_sets_cookie(client):
    qid = db.create_question("Vote me", None)
    r = client.post(f"/questions/{qid}/upvote")
    assert r.status_code == 200
    assert "▲ 1" in r.text
    assert "disabled" in r.text
    assert db.list_questions()[0]["votes"] == 1
    assert r.cookies.get("voted") == str(qid)


def test_upvote_only_once_per_browser(client):
    qid = db.create_question("Vote me", None)
    client.post(f"/questions/{qid}/upvote")
    r = client.post(f"/questions/{qid}/upvote")
    assert r.status_code == 200
    assert db.list_questions()[0]["votes"] == 1


def test_upvote_from_another_browser_counts(client):
    qid = db.create_question("Vote me", None)
    client.post(f"/questions/{qid}/upvote")
    client.cookies.clear()
    client.post(f"/questions/{qid}/upvote")
    assert db.list_questions()[0]["votes"] == 2


def test_upvote_tracks_multiple_questions(client):
    a = db.create_question("A", None)
    b = db.create_question("B", None)
    client.post(f"/questions/{a}/upvote")
    r = client.post(f"/questions/{b}/upvote")
    assert r.text.count("disabled") == 2
    assert all(q["votes"] == 1 for q in db.list_questions())


def test_polling_partial_keeps_voted_state(client):
    qid = db.create_question("Vote me", None)
    client.post(f"/questions/{qid}/upvote")
    assert "disabled" in client.get("/questions").text


def test_upvote_missing_question_returns_404(client):
    r = client.post("/questions/999/upvote")
    assert r.status_code == 404
    assert "voted" not in r.cookies


def test_upvote_invalid_id_returns_422(client):
    r = client.post("/questions/abc/upvote")
    assert r.status_code == 422


def test_upvote_ignores_malformed_cookie(client):
    qid = db.create_question("Vote me", None)
    client.cookies.set("voted", "junk.x.")
    r = client.post(f"/questions/{qid}/upvote")
    assert r.status_code == 200
    assert db.list_questions()[0]["votes"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        '<img src=x onerror="alert(1)">',
        '<div hx-post="/questions/1/upvote" hx-trigger="every 1s">x</div>',
    ],
)
def test_question_html_is_escaped_in_page_and_partial(client, payload):
    client.post("/questions", data={"text": payload})
    for path in ("/", "/questions"):
        body = client.get(path).text
        assert payload not in body
        assert str(escape(payload)) in body
