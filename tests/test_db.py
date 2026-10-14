import json

from app import db


def test_list_newest_first_with_id_tiebreak():
    db.init_db()
    for title in ["a", "b", "c"]:
        db.add_topic(title, None, "attendee")
    assert [t["title"] for t in db.list_topics()] == ["c", "b", "a"]


def test_load_organizer_topics_is_idempotent(tmp_path):
    f = tmp_path / "topics.json"
    f.write_text(json.dumps([{"title": "One"}, {"title": "Two"}]))
    db.init_db()
    for _ in range(3):
        db.init_db()
        db.load_organizer_topics(str(f))
    topics = db.list_topics()
    assert sorted(t["title"] for t in topics) == ["One", "Two"]
    assert all(t["source"] == "organizer" for t in topics)


def test_load_skips_invalid_entries(tmp_path):
    f = tmp_path / "topics.json"
    f.write_text(
        json.dumps([{"title": "  "}, {"title": "x" * 281}, {}, {"title": "ok"}])
    )
    db.init_db()
    db.load_organizer_topics(str(f))
    assert [t["title"] for t in db.list_topics()] == ["ok"]


def test_attendee_duplicates_allowed_and_blank_author_is_null():
    db.init_db()
    db.add_topic("same", "", "attendee")
    db.add_topic("same", "Ann", "attendee")
    topics = db.list_topics()
    assert len(topics) == 2
    assert topics[1]["author"] is None
