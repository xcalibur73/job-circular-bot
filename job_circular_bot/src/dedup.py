"""
Keeps track of which notices have already been posted, so the same job
circular never gets posted to the Facebook Page twice.

Uses a small SQLite file as the "memory" of the bot. On GitHub Actions (or any
environment that resets between runs), this file must be persisted between
runs -- the workflow restores and saves it with actions/cache, so it never has
to be committed to the repository.

Two things are remembered: notices that were posted, and notices that the
guardrails rejected. Flagged notices are recorded as well as skipped, otherwise
the same broken listing would be re-alerted on every single run.
"""

import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "posted.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posted_notices (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            url TEXT,
            posted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flagged_notices (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            url TEXT,
            reason TEXT,
            flagged_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_state (
            url TEXT PRIMARY KEY,
            last_polled TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerted_sources (
            url TEXT PRIMARY KEY,
            last_alerted TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


def notice_id(notice):
    """A stable fingerprint for a notice, based on its URL (and title as backup).

    Using the URL as the primary key means even if a site changes the page title
    slightly on a re-crawl, we still recognize it as the same notice.
    """
    raw = notice.get("url") or notice.get("title", "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def filter_new(notices):
    """Return only the notices that have not been posted or flagged before."""
    conn = _connect()
    new_notices = []
    for notice in notices:
        nid = notice_id(notice)
        exists = conn.execute(
            "SELECT 1 FROM posted_notices WHERE id = ?"
            " UNION ALL SELECT 1 FROM flagged_notices WHERE id = ?",
            (nid, nid),
        ).fetchone()
        if not exists:
            new_notices.append(notice)
    conn.close()
    return new_notices


def mark_posted(notice):
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO posted_notices (id, source, title, url) VALUES (?, ?, ?, ?)",
        (notice_id(notice), notice["source"], notice["title"], notice["url"]),
    )
    conn.commit()
    conn.close()


def mark_flagged(notice, reason):
    """Remember a notice the guardrails rejected, so it is only alerted on once."""
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO flagged_notices (id, source, title, url, reason)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            notice_id(notice),
            notice.get("source"),
            notice.get("title"),
            notice.get("url"),
            reason,
        ),
    )
    conn.commit()
    conn.close()


def should_poll(url, min_interval_minutes, now=None):
    """True when enough time has passed since this source was last fetched.

    Public job APIs publish fair-use limits (Remotive asks for about 4 pulls a
    day, Jobicy for at most one per hour). min_interval_minutes=0 always
    returns True.
    """
    if not min_interval_minutes or min_interval_minutes <= 0:
        return True

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT last_polled FROM source_state WHERE url = ?", (url,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return True

    try:
        last = datetime.fromisoformat(row[0])
    except (TypeError, ValueError):
        return True

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - last).total_seconds() >= min_interval_minutes * 60


def mark_polled(url):
    """Records that a source was fetched right now (UTC, like CURRENT_TIMESTAMP)."""
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO source_state (url, last_polled) VALUES (?, ?)",
        (url, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def should_alert_source(url, min_hours=24, now=None):
    """True when a broken source should trigger a Telegram alert again.

    A source that stays broken would otherwise alert on every run, every 30
    minutes, forever. Reminding once a day is enough to get it fixed without
    training the user to ignore the bell.
    """
    if not min_hours or min_hours <= 0:
        return True

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT last_alerted FROM alerted_sources WHERE url = ?", (url,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return True

    try:
        last = datetime.fromisoformat(row[0])
    except (TypeError, ValueError):
        return True

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - last).total_seconds() >= min_hours * 3600


def mark_source_alerted(url):
    """Records that a source failure was just alerted on."""
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO alerted_sources (url, last_alerted) VALUES (?, ?)",
        (url, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()
