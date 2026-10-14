import sqlite3
from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from markupsafe import escape

from app import db
from app.moderation import ADMIN_USERNAME, router

PASSWORD = "s3cret-pass"
AUTH = (ADMIN_USERNAME, PASSWORD)
HTMX = {"HX-Request": "true"}


@pytest.fixture
def mod_client(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    app = FastAPI()
    app.include_router(router)
    db.init_db()
    with TestClient(app) as c:
        yield c


# --- db layer -------------------------------------------------------------


def test_new_questions_are_unanswered(mod_client):
    db.create_question("Q", None)
    assert db.list_questions()[0]["answered"] == 0


def test_mark_answered_db(mod_client):
    qid = db.create_question("Q", None)
    assert db.mark_answered(qid) is True
    assert db.list_questions()[0]["answered"] == 1
    assert db.mark_answered(999) is False


def test_delete_question_db(mod_client):
    qid = db.create_question("Q", None)
    assert db.delete_question(qid) is True
    assert db.list_questions() == []
    assert db.delete_question(qid) is False


def test_answered_sorted_last_even_with_more_votes(mod_client):
    popular = db.create_question("popular", None)
    db.create_question("plain", None)
    for _ in range(5):
        db.upvote_question(popular)
    db.mark_answered(popular)
    assert [q["text"] for q in db.list_questions()] == ["plain", "popular"]


def test_init_db_migrates_table_without_answered_column():
    with closing(sqlite3.connect(db.db_path())) as conn, conn:
        conn.execute(
            """
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                author TEXT,
                votes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        conn.execute("INSERT INTO questions (text) VALUES ('legacy')")
    db.init_db()
    db.init_db()  # idempotent
    [q] = db.list_questions()
    assert q["text"] == "legacy"
    assert q["answered"] == 0


# --- auth -----------------------------------------------------------------


def test_moderate_page_requires_auth(mod_client):
    r = mod_client.get("/moderate")
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Basic")


@pytest.mark.parametrize(
    "auth",
    [(ADMIN_USERNAME, "wrong"), ("someone", PASSWORD), (ADMIN_USERNAME, "")],
)
def test_moderate_page_rejects_bad_credentials(mod_client, auth):
    assert mod_client.get("/moderate", auth=auth).status_code == 401


def test_non_ascii_password_does_not_crash(mod_client):
    assert (
        mod_client.get("/moderate", auth=(ADMIN_USERNAME, "pässwörd")).status_code
        == 401
    )


@pytest.mark.parametrize("value", [None, ""])
def test_access_denied_when_admin_password_unset(mod_client, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ADMIN_PASSWORD")
    else:
        monkeypatch.setenv("ADMIN_PASSWORD", value)
    qid = db.create_question("Q", None)
    assert mod_client.get("/moderate", auth=(ADMIN_USERNAME, "")).status_code == 403
    r = mod_client.post(
        f"/moderate/questions/{qid}/answered", auth=(ADMIN_USERNAME, ""), headers=HTMX
    )
    assert r.status_code == 403
    r = mod_client.delete(
        f"/moderate/questions/{qid}", auth=(ADMIN_USERNAME, ""), headers=HTMX
    )
    assert r.status_code == 403
    assert db.list_questions()[0]["answered"] == 0


def test_actions_require_auth(mod_client):
    qid = db.create_question("Q", None)
    r = mod_client.post(f"/moderate/questions/{qid}/answered", headers=HTMX)
    assert r.status_code == 401
    r = mod_client.delete(f"/moderate/questions/{qid}", headers=HTMX)
    assert r.status_code == 401
    r = mod_client.get("/moderate/questions")
    assert r.status_code == 401
    [q] = db.list_questions()
    assert q["answered"] == 0


# --- page -----------------------------------------------------------------


def test_moderate_page_renders(mod_client):
    db.create_question("What is htmx?", "Ada")
    r = mod_client.get("/moderate", auth=AUTH)
    assert r.status_code == 200
    assert "What is htmx?" in r.text
    assert 'hx-get="/moderate/questions"' in r.text
    assert "Mark answered" in r.text
    assert "hx-delete=" in r.text
    assert "/upvote" not in r.text


def test_moderate_partial(mod_client):
    db.create_question("First", None)
    r = mod_client.get("/moderate/questions", auth=AUTH)
    assert r.status_code == 200
    assert "First" in r.text
    assert "<html" not in r.text


def test_moderate_page_escapes_question_text(mod_client):
    payload = "<script>alert(1)</script>"
    db.create_question(payload, payload)
    r = mod_client.get("/moderate", auth=AUTH)
    assert payload not in r.text
    assert str(escape(payload)) in r.text


# --- mark answered --------------------------------------------------------


def test_mark_answered_happy_path(mod_client):
    qid = db.create_question("Q", None)
    r = mod_client.post(f"/moderate/questions/{qid}/answered", auth=AUTH, headers=HTMX)
    assert r.status_code == 200
    assert "<html" not in r.text
    assert 'class="answered"' in r.text
    assert db.list_questions()[0]["answered"] == 1


def test_mark_answered_not_found(mod_client):
    r = mod_client.post("/moderate/questions/999/answered", auth=AUTH, headers=HTMX)
    assert r.status_code == 404


def test_mark_answered_invalid_id(mod_client):
    r = mod_client.post("/moderate/questions/abc/answered", auth=AUTH, headers=HTMX)
    assert r.status_code == 422


# --- delete ---------------------------------------------------------------


def test_delete_happy_path(mod_client):
    qid = db.create_question("Doomed", None)
    db.create_question("Kept", None)
    r = mod_client.delete(f"/moderate/questions/{qid}", auth=AUTH, headers=HTMX)
    assert r.status_code == 200
    assert "Doomed" not in r.text
    assert "Kept" in r.text
    assert [q["text"] for q in db.list_questions()] == ["Kept"]


def test_delete_not_found(mod_client):
    r = mod_client.delete("/moderate/questions/999", auth=AUTH, headers=HTMX)
    assert r.status_code == 404


def test_delete_invalid_id(mod_client):
    r = mod_client.delete("/moderate/questions/abc", auth=AUTH, headers=HTMX)
    assert r.status_code == 422


# --- CSRF -----------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"HX-Request": "false"},
        {**HTMX, "Origin": "https://evil.example"},
        {**HTMX, "Sec-Fetch-Site": "cross-site"},
        {**HTMX, "Sec-Fetch-Site": "same-site"},
    ],
)
def test_actions_reject_cross_site_requests(mod_client, headers):
    qid = db.create_question("Q", None)
    r = mod_client.post(
        f"/moderate/questions/{qid}/answered", auth=AUTH, headers=headers
    )
    assert r.status_code == 403
    r = mod_client.delete(f"/moderate/questions/{qid}", auth=AUTH, headers=headers)
    assert r.status_code == 403
    [q] = db.list_questions()
    assert q["answered"] == 0


def test_actions_accept_same_origin(mod_client):
    qid = db.create_question("Q", None)
    headers = {**HTMX, "Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"}
    r = mod_client.post(
        f"/moderate/questions/{qid}/answered", auth=AUTH, headers=headers
    )
    assert r.status_code == 200


# --- audience view --------------------------------------------------------


def test_audience_partial_greys_out_answered(client):
    qid = db.create_question("Done", None)
    db.create_question("Open", None)
    db.mark_answered(qid)
    r = client.get("/questions")
    assert r.status_code == 200
    assert r.text.index("Open") < r.text.index("Done")
    assert 'class="answered"' in r.text
    assert "Mark answered" not in r.text
    assert "hx-delete" not in r.text


def test_upvote_still_works_on_answered_question(client):
    qid = db.create_question("Done", None)
    db.mark_answered(qid)
    r = client.post(f"/questions/{qid}/upvote")
    assert r.status_code == 200
    assert db.list_questions()[0]["votes"] == 1


# --- clickjacking ---------------------------------------------------------


def assert_no_frame_headers(r):
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"] == "frame-ancestors 'none'"


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "expected"),
    [
        ("get", "/moderate", {"auth": AUTH}, 200),
        ("get", "/moderate/questions", {"auth": AUTH}, 200),
        ("get", "/moderate", {}, 401),
        ("get", "/moderate", {"auth": (ADMIN_USERNAME, "wrong")}, 401),
        ("post", "/moderate/questions/{qid}/answered", {"auth": AUTH}, 403),
        ("post", "/moderate/questions/999/answered", {"auth": AUTH}, 404),
        ("post", "/moderate/questions/abc/answered", {"auth": AUTH}, 422),
        ("post", "/moderate/questions/{qid}/answered", {"auth": AUTH}, 200),
        ("delete", "/moderate/questions/999", {"auth": AUTH}, 404),
        ("delete", "/moderate/questions/abc", {"auth": AUTH}, 422),
        ("delete", "/moderate/questions/{qid}", {"auth": AUTH}, 200),
    ],
)
def test_moderate_responses_forbid_framing(mod_client, method, path, kwargs, expected):
    qid = db.create_question("Q", None)
    headers = HTMX if method != "get" and expected != 403 else {}
    r = getattr(mod_client, method)(path.format(qid=qid), headers=headers, **kwargs)
    assert r.status_code == expected
    assert_no_frame_headers(r)


def test_forbid_framing_when_admin_password_unset(mod_client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD")
    r = mod_client.get("/moderate", auth=AUTH)
    assert r.status_code == 403
    assert_no_frame_headers(r)
