import pytest

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
