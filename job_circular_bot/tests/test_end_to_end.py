"""End-to-end smoke test.

Serves tests/fixtures/listings.html over localhost, points the real
orchestration flow at it through a company_site_list.txt written on the fly,
and checks the outcome of full runs: what gets posted, what gets alerted on,
and what the second run does.

No network access beyond localhost, and no Facebook credentials.
"""

import functools
import http.server
import socketserver
import sqlite3
import threading
from pathlib import Path

import pytest

import dedup
import facebook_poster
import main as bot_main
import site_list
import scraper

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the test output readable


@pytest.fixture
def local_site():
    handler = functools.partial(_QuietHandler, directory=str(FIXTURES))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()


@pytest.fixture
def isolated(tmp_path, monkeypatch, local_site):
    """One good source, one broken source, a throwaway database."""
    sites_file = tmp_path / "company_site_list.txt"
    sites_file.write_text(
        f"{local_site}/listings.html\n"
        f"{local_site}/missing.html\n",
        encoding="utf-8",
    )

    alerts = []
    monkeypatch.setattr(site_list, "SITES_PATH", sites_file)
    monkeypatch.setattr(dedup, "DB_PATH", tmp_path / "posted.db")
    monkeypatch.setattr(bot_main, "send_alert", alerts.append)
    monkeypatch.setattr(scraper, "DELAY_BETWEEN_SOURCES_SECONDS", 0)
    return alerts


def test_full_run_posts_once_then_never_again(isolated, monkeypatch):
    posted_urls = []

    class FakeGraphResponse:
        status_code = 200
        text = '{"id": "1_2"}'

        def json(self):
            return {"id": "1_2"}

    def fake_post(url, data=None, timeout=None):
        posted_urls.append(data["link"])
        return FakeGraphResponse()

    monkeypatch.setattr(facebook_poster, "DRY_RUN", False)
    monkeypatch.setattr(facebook_poster, "PAGE_ID", "1234567890")
    monkeypatch.setattr(facebook_poster, "PAGE_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr(facebook_poster.requests, "post", fake_post)

    bot_main.run(respect_intervals=False)

    # The two job links on the fixture page are posted; the broken source is
    # alerted on, not posted, and the navigation links are never candidates.
    assert len(posted_urls) == 2
    assert all("/jobs/" in url for url in posted_urls)
    assert len(isolated) == 1
    assert "Failed to fetch" in isolated[0]

    # Second run: the same page is fetched again, but everything is known now.
    posted_urls.clear()
    alerts_before = len(isolated)
    bot_main.run(respect_intervals=False)

    assert posted_urls == []
    assert len(isolated) == alerts_before


def test_a_keyword_that_matches_nothing_posts_nothing(isolated, monkeypatch):
    monkeypatch.setattr(facebook_poster, "DRY_RUN", True)

    bot_main.run(keyword="marine biologist", respect_intervals=False)

    conn = sqlite3.connect(dedup.DB_PATH)
    try:
        posted = conn.execute("SELECT COUNT(*) FROM posted_notices").fetchone()[0]
    finally:
        conn.close()

    assert posted == 0
    # The only alert is about the deliberately broken source; unrelated
    # notices are dropped quietly, with no alert and nothing remembered.
    assert len(isolated) == 1
    assert "Failed to fetch" in isolated[0]


def test_dry_run_fetches_but_records_nothing(isolated, monkeypatch):
    monkeypatch.setattr(facebook_poster, "DRY_RUN", True)

    bot_main.run(respect_intervals=False)

    conn = sqlite3.connect(dedup.DB_PATH)
    try:
        posted = conn.execute("SELECT COUNT(*) FROM posted_notices").fetchone()[0]
    finally:
        conn.close()

    assert posted == 0
