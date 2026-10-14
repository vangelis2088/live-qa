"""Markdown export of all questions (GET /export.md)."""

import string
import unicodedata

from fastapi import APIRouter
from fastapi.responses import Response

from app import db

router = APIRouter()

EXPORT_FILENAME = "qa-export.md"
MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"

# CommonMark allows any ASCII punctuation character to be backslash-escaped,
# and an escaped character is always rendered as literal text.
_ESCAPE = str.maketrans({ch: "\\" + ch for ch in string.punctuation})


def escape_markdown(value: str) -> str:
    """Render untrusted text as one line of inert Markdown text."""
    value = "".join(
        ch
        for ch in value
        if not unicodedata.category(ch).startswith("C") or ch.isspace()
    )
    # Collapse every kind of whitespace (newlines, tabs, U+2028, ...) to a
    # single space so the text can't start new blocks or break the list.
    value = " ".join(value.split())
    return value.translate(_ESCAPE)


def _sort_key(question: dict) -> tuple:
    return (-int(question["votes"]), -int(question["id"]))


def render_markdown(questions: list[dict]) -> str:
    """Build the Markdown document for the given questions."""
    lines = ["# Live Q&A export", ""]
    if not questions:
        lines.append("No questions yet.")
        return "\n".join(lines) + "\n"

    count = len(questions)
    lines.append(f"{count} question{'' if count == 1 else 's'}, sorted by votes.")
    lines.append("")
    for position, question in enumerate(sorted(questions, key=_sort_key), start=1):
        text = escape_markdown(question["text"] or "") or "(empty)"
        author = escape_markdown(question.get("author") or "") or "Anonymous"
        votes = int(question["votes"])
        status = "✅ Answered" if question.get("answered") else "Open"
        lines.append(f"{position}. {text}")
        lines.append(f"   - Author: {author}")
        lines.append(f"   - Votes: {votes}")
        lines.append(f"   - Status: {status}")
    return "\n".join(lines) + "\n"


@router.get("/export.md")
def export_markdown() -> Response:
    """Download all questions as a Markdown file, sorted by votes."""
    return Response(
        content=render_markdown(db.list_questions()),
        media_type=MARKDOWN_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{EXPORT_FILENAME}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
