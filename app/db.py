import os
import sqlite3
from contextlib import closing

MAX_TEXT_LEN = 280
MAX_AUTHOR_LEN = 50


def db_path() -> str:
    return os.environ.get("QA_DB_PATH", "qa.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(connect()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                author TEXT,
                votes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                answered INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(questions)")}
        if "answered" not in columns:
            conn.execute(
                "ALTER TABLE questions ADD COLUMN answered INTEGER NOT NULL DEFAULT 0"
            )


def create_question(text: str, author: str | None) -> int:
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO questions (text, author) VALUES (?, ?)", (text, author)
        )
        return cur.lastrowid


def list_questions() -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute(
            """
            SELECT id, text, author, votes, created_at, answered
            FROM questions
            ORDER BY answered ASC, votes DESC, created_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def upvote_question(question_id: int) -> bool:
    """Add one vote to a question; return False if it does not exist."""
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE questions SET votes = votes + 1 WHERE id = ?", (question_id,)
        )
        return cur.rowcount > 0


def mark_answered(question_id: int) -> bool:
    """Mark a question as answered; return False if it does not exist."""
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE questions SET answered = 1 WHERE id = ?", (question_id,)
        )
        return cur.rowcount > 0


def delete_question(question_id: int) -> bool:
    """Delete a question; return False if it does not exist."""
    with closing(connect()) as conn, conn:
        cur = conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        return cur.rowcount > 0


def question_exists(question_id: int) -> bool:
    """Return True if a question with this id exists."""
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT 1 FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
    return row is not None
