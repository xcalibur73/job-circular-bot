"""The dedup layer is what stops the same circular being posted twice, so it is
worth testing directly rather than trusting a live run."""

import pytest

import dedup


def _notice(url="https://example.com/jobs/1", title="Backend Engineer"):
    return {"source": "Example Ltd", "title": title, "url": url}


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Never touch the real data/posted.db."""
    monkeypatch.setattr(dedup, "DB_PATH", tmp_path / "posted.db")


def test_notice_id_is_stable_for_the_same_url():
    assert dedup.notice_id(_notice()) == dedup.notice_id(_notice(title="Backend Engineer (updated)"))


def test_notice_id_differs_for_different_urls():
    assert dedup.notice_id(_notice()) != dedup.notice_id(_notice(url="https://example.com/jobs/2"))


def test_notice_id_falls_back_to_the_title_without_a_url():
    assert dedup.notice_id({"title": "No link here"}) == dedup.notice_id({"title": "No link here"})
    assert dedup.notice_id({"title": "No link here"}) != dedup.notice_id({"title": "Something else"})


def test_unseen_notice_is_new_then_not_new_again():
    notice = _notice()

    assert dedup.filter_new([notice]) == [notice]

    dedup.mark_posted(notice)
    assert dedup.filter_new([notice]) == []


def test_flagged_notice_is_not_returned_again():
    notice = _notice()

    dedup.mark_flagged(notice, "title length looks wrong (2 chars)")

    assert dedup.filter_new([notice]) == []


def test_mark_flagged_stores_the_reason():
    notice = _notice()
    dedup.mark_flagged(notice, "missing or invalid URL")

    conn = dedup._connect()
    try:
        row = conn.execute(
            "SELECT reason FROM flagged_notices WHERE id = ?", (dedup.notice_id(notice),)
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == "missing or invalid URL"


def test_marking_the_same_flagged_notice_twice_is_safe():
    notice = _notice()
    dedup.mark_flagged(notice, "first reason")
    dedup.mark_flagged(notice, "second reason")

    conn = dedup._connect()
    try:
        count = conn.execute("SELECT COUNT(*) FROM flagged_notices").fetchone()[0]
    finally:
        conn.close()

    assert count == 1
