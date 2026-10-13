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
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
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
            SELECT id, text, author, votes, created_at
            FROM questions
            ORDER BY votes DESC, created_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]
