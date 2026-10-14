import json
import os
import sqlite3

MAX_TITLE_LEN = 280


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ.get("QA_DB_PATH", "qa.db"))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND {MAX_TITLE_LEN}),
                author TEXT,
                source TEXT NOT NULL CHECK(source IN ('organizer', 'attendee')),
                created_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_topics_organizer_title "
            "ON topics(title) WHERE source = 'organizer'"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY,
                voter_id TEXT NOT NULL UNIQUE,
                topic_id INTEGER NOT NULL REFERENCES topics(id),
                created_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
            )
            """
        )
    conn.close()


def cast_vote(voter_id: str, topic_id: int) -> bool:
    """Set the voter's single vote to topic_id; False if the topic doesn't exist."""
    conn = get_conn()
    try:
        with conn:
            if not conn.execute(
                "SELECT 1 FROM topics WHERE id = ?", (topic_id,)
            ).fetchone():
                return False
            conn.execute(
                "INSERT INTO votes (voter_id, topic_id) VALUES (?, ?) "
                "ON CONFLICT(voter_id) DO UPDATE SET topic_id = excluded.topic_id "
                "WHERE votes.topic_id != excluded.topic_id",
                (voter_id, topic_id),
            )
        return True
    finally:
        conn.close()


def add_topic(title: str, author: str | None, source: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO topics (title, author, source) VALUES (?, ?, ?)",
            (title, author or None, source),
        )
    conn.close()


def list_topics(voter_id: str | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(
            """
            SELECT t.id, t.title, t.author, t.source, t.created_at,
                   (SELECT COUNT(*) FROM votes v WHERE v.topic_id = t.id) AS votes,
                   EXISTS(SELECT 1 FROM votes v
                          WHERE v.topic_id = t.id AND v.voter_id = ?) AS voted
            FROM topics t
            ORDER BY votes DESC, t.created_at DESC, t.id DESC
            """,
            (voter_id or "",),
        ).fetchall()
    finally:
        conn.close()


def load_organizer_topics(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    conn = get_conn()
    try:
        with conn:
            for item in items:
                title = str(item.get("title", "")).strip()
                if not title or len(title) > MAX_TITLE_LEN:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO topics (title, author, source) "
                    "VALUES (?, NULL, 'organizer')",
                    (title,),
                )
    finally:
        conn.close()
