from contextlib import closing

import pytest

from app import db


@pytest.fixture(autouse=True)
def schema():
    db.init_db()


def set_votes(question_id, votes):
    # No upvote feature yet, so set votes directly for ordering tests.
    with closing(db.connect()) as conn, conn:
        conn.execute(
            "UPDATE questions SET votes = ? WHERE id = ?", (votes, question_id)
        )


def test_create_question_defaults():
    qid = db.create_question("Hello?", None)
    [q] = db.list_questions()
    assert q["id"] == qid
    assert q["text"] == "Hello?"
    assert q["author"] is None
    assert q["votes"] == 0
    assert q["created_at"]


def test_newest_first_when_votes_equal():
    db.create_question("old", None)
    db.create_question("middle", None)
    db.create_question("new", None)
    assert [q["text"] for q in db.list_questions()] == ["new", "middle", "old"]


def test_votes_take_precedence_over_age():
    popular = db.create_question("popular", None)
    db.create_question("old", None)
    db.create_question("new", None)
    set_votes(popular, 5)
    assert [q["text"] for q in db.list_questions()] == ["popular", "new", "old"]


def test_upvote_question():
    qid = db.create_question("Hello?", None)
    assert db.upvote_question(qid) is True
    assert db.list_questions()[0]["votes"] == 1


def test_upvote_missing_question():
    assert db.upvote_question(999) is False


def test_question_exists():
    qid = db.create_question("Hello?", None)
    assert db.question_exists(qid) is True
    assert db.question_exists(999) is False
