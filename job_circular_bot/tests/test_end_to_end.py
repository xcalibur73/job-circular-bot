"""End-to-end smoke test.

Serves tests/fixtures/listings.html over localhost, points the real
orchestration flow at it, and checks the outcome of a full run: what gets
posted, what gets flagged, and what the second run does.

No network access and no Facebook credentials are involved.
"""

import functools
import http.server
import sqlite3
import socketserver
import threading
from pathlib import Path

import pytest
import yaml

import dedup
import facebook_poster
import main as bot_main
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
def fixture_config(tmp_path, local_site):
    config = {
        "sources": [{
            "name": "Fixture Company",
            "url": f"{local_site}/listings.html",
            "parser": "static_html",
            "selectors": {
                "list_item": "div.job",
                "title": "h3",
                "link": "a",
                "date": "span.date",
            },
            "link_is_relative": True,
        }]
    }
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


@pytest.fixture
def isolated(tmp_path, monkeypatch, fixture_config):
    """Point the bot at the fixture page and at a throwaway database."""
    alerts = []
    monkeypatch.setattr(bot_main, "CONFIG_PATH", fixture_config)
    monkeypatch.setattr(dedup, "DB_PATH", tmp_path / "posted.db")
    monkeypatch.setattr(bot_main, "send_alert", alerts.append)
    monkeypatch.setattr(scraper, "DELAY_BETWEEN_SOURCES_SECONDS", 0)
    return alerts


def test_dry_run_fetches_flags_but_records_nothing(isolated, monkeypatch):
    monkeypatch.setattr(facebook_poster, "DRY_RUN", True)

    bot_main.run()

    # One notice is unusable (no title), so it is flagged and alerted on.
    assert len(isolated) == 1
    assert "Flagged and skipped" in isolated[0]

    # Nothing was posted, so nothing may be recorded: a later real run still
    # has to be able to post these notices.
    conn = sqlite3.connect(dedup.DB_PATH)
    try:
        posted = conn.execute("SELECT COUNT(*) FROM posted_notices").fetchone()[0]
        flagged = conn.execute("SELECT COUNT(*) FROM flagged_notices").fetchone()[0]
    finally:
        conn.close()

    assert posted == 0
    assert flagged == 1


class _FakeResponse:
    status_code = 200
    text = '{"id": "1_2"}'

    def json(self):
        return {"id": "1_2"}


def test_real_runs_post_once_and_never_again(isolated, monkeypatch):
    posted_urls = []

    def fake_post(url, data=None, timeout=None):
        posted_urls.append(data["link"])
        return _FakeResponse()

    monkeypatch.setattr(facebook_poster, "DRY_RUN", False)
    monkeypatch.setattr(facebook_poster, "PAGE_ID", "1234567890")
    monkeypatch.setattr(facebook_poster, "PAGE_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr(facebook_poster.requests, "post", fake_post)

    bot_main.run()

    # Two valid listings posted, the title-less one flagged instead.
    assert len(posted_urls) == 2
    assert all("/jobs/" in url for url in posted_urls)
    assert len(isolated) == 1

    # Second run: the same page is fetched again, but everything is known now.
    posted_urls.clear()
    flagged_before = len(isolated)
    bot_main.run()

    assert posted_urls == []
    assert len(isolated) == flagged_before, "a flagged notice must not alert twice"
