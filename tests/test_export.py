import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.export import escape_markdown, render_markdown, router


@pytest.fixture
def export_client():
    app = FastAPI()
    app.include_router(router)
    db.init_db()
    with TestClient(app) as c:
        yield c


def add(text: str, author: str | None = None, votes: int = 0) -> int:
    qid = db.create_question(text, author)
    for _ in range(votes):
        db.upvote_question(qid)
    return qid


def item_lines(body: str) -> list[str]:
    """Return the top-level numbered list lines of the export."""
    return [line for line in body.splitlines() if re.match(r"\d+\. ", line)]


def test_export_content_type_and_download_header(export_client):
    resp = export_client.get("/export.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment")
    assert 'filename="qa-export.md"' in disposition
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_export_empty(export_client):
    resp = export_client.get("/export.md")
    assert resp.status_code == 200
    assert "# Live Q&A export" in resp.text
    assert "No questions yet." in resp.text
    assert item_lines(resp.text) == []


def test_export_sorted_by_votes_desc(export_client):
    add("low", votes=1)
    add("high", votes=5)
    add("mid", votes=3)
    add("zero")
    lines = item_lines(export_client.get("/export.md").text)
    assert lines == ["1. high", "2. mid", "3. low", "4. zero"]


def test_export_tie_break_is_stable_newest_first(export_client):
    add("first", votes=2)
    add("second", votes=2)
    add("third", votes=2)
    lines = item_lines(export_client.get("/export.md").text)
    assert lines == ["1. third", "2. second", "3. first"]


def test_export_sort_ignores_input_order():
    questions = [
        {"id": 1, "text": "answered top", "author": None, "votes": 9, "answered": 1},
        {"id": 2, "text": "open low", "author": None, "votes": 1, "answered": 0},
        {"id": 3, "text": "open mid", "author": None, "votes": 4, "answered": 0},
    ]
    # Simulate list_questions putting answered questions last.
    reordered = [questions[2], questions[1], questions[0]]
    lines = item_lines(render_markdown(reordered))
    assert lines == ["1. answered top", "2. open mid", "3. open low"]


def test_export_author_votes_and_anonymous(export_client):
    add("named", author="Alice", votes=2)
    add("nameless", votes=1)
    body = export_client.get("/export.md").text
    assert "1. named\n   - Author: Alice\n   - Votes: 2\n" in body
    assert "2. nameless\n   - Author: Anonymous\n   - Votes: 1\n" in body
    assert "2 questions" in body


def test_export_answered_marker():
    questions = [
        {"id": 1, "text": "done", "author": None, "votes": 2, "answered": 1},
        {"id": 2, "text": "pending", "author": None, "votes": 1, "answered": 0},
        {"id": 3, "text": "legacy", "author": None, "votes": 0},
    ]
    body = render_markdown(questions)
    assert (
        "1. done\n   - Author: Anonymous\n   - Votes: 2\n   - Status: ✅ Answered"
        in body
    )
    assert (
        "2. pending\n   - Author: Anonymous\n   - Votes: 1\n   - Status: Open" in body
    )
    assert "3. legacy\n   - Author: Anonymous\n   - Votes: 0\n   - Status: Open" in body
    assert body.count("✅ Answered") == 1


def test_export_answered_end_to_end_sorted_by_votes(export_client):
    top = add("answered but popular", votes=3)
    add("open and quiet", votes=1)
    assert db.mark_answered(top)
    body = export_client.get("/export.md").text
    # list_questions puts answered last; the export still sorts by votes.
    assert item_lines(body) == ["1. answered but popular", "2. open and quiet"]
    assert "1. answered but popular\n   - Author: Anonymous\n   - Votes: 3\n" in body
    assert "   - Votes: 3\n   - Status: ✅ Answered\n" in body
    assert "   - Votes: 1\n   - Status: Open\n" in body


def test_export_shows_open_status_for_new_question(export_client):
    add("fresh")
    assert "- Status: Open" in export_client.get("/export.md").text


@pytest.mark.parametrize(
    "payload",
    [
        "# Heading",
        "[click](https://evil.example)",
        "![img](https://evil.example/x.png)",
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "**bold** _em_ `code`",
        "- fake item",
        "1. fake item",
        "> quote",
        "| a | b |",
        "&lt;b&gt;",
    ],
)
def test_escape_markdown_neutralises_syntax(payload):
    escaped = escape_markdown(payload)
    # Every punctuation character is backslash-escaped, so none is live.
    for i, ch in enumerate(escaped):
        if ch in "#[]()!<>*_`-|&>.":
            assert escaped[i - 1] == "\\", (payload, escaped)


def test_export_neutralises_injection_and_newlines(export_client):
    add(
        "line one\n# Injected heading\n\n- fake item\r\n<script>alert(1)</script>",
        author="[Bob](https://evil.example)\n## boom",
        votes=1,
    )
    body = export_client.get("/export.md").text
    lines = body.splitlines()
    # The question occupies exactly one list item of four lines.
    start = lines.index(next(line for line in lines if line.startswith("1. ")))
    item = lines[start : start + 4]
    assert item[0] == (
        r"1. line one \# Injected heading \- fake item "
        r"\<script\>alert\(1\)\<\/script\>"
    )
    assert item[1] == r"   - Author: \[Bob\]\(https\:\/\/evil\.example\) \#\# boom"
    assert item[2] == "   - Votes: 1"
    assert item[3] == "   - Status: Open"
    assert "<script>" not in body
    assert "](" not in body
    # Only our own heading is a heading.
    assert [line for line in lines if line.startswith("#")] == ["# Live Q&A export"]


def test_escape_markdown_collapses_unicode_line_breaks_and_controls():
    assert escape_markdown("a b c\x0bd\x85e\tf") == "a b c d e f"
    assert escape_markdown("a\x00b\x1bc") == "abc"
    assert escape_markdown("   ") == ""
