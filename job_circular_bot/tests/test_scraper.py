"""A failing source must be reported, not just logged, and must never stop the
remaining sources from being checked."""

import scraper


def test_failed_source_is_reported_and_does_not_stop_the_run(monkeypatch):
    def explode(source):
        raise RuntimeError("site changed its layout")

    working = [{
        "source": "Working Ltd",
        "title": "Backend Engineer",
        "url": "https://working.example/jobs/1",
        "posted_date": None,
    }]

    monkeypatch.setattr(scraper, "DELAY_BETWEEN_SOURCES_SECONDS", 0)
    monkeypatch.setitem(scraper.PARSERS, "static_html", explode)
    monkeypatch.setitem(scraper.PARSERS, "rss", lambda source: working)

    failures = []
    notices = scraper.fetch_all(
        [
            {"name": "Broken Ltd", "url": "https://broken.example/careers", "parser": "static_html"},
            {"name": "Working Ltd", "url": "https://working.example/feed.xml", "parser": "rss"},
        ],
        on_failure=failures.append,
    )

    assert notices == working
    assert len(failures) == 1
    assert "Broken Ltd" in failures[0]
    assert "site changed its layout" in failures[0]


def test_unknown_parser_is_skipped_without_reporting_a_failure(monkeypatch):
    monkeypatch.setattr(scraper, "DELAY_BETWEEN_SOURCES_SECONDS", 0)

    failures = []
    notices = scraper.fetch_all(
        [{"name": "Typo Ltd", "url": "https://typo.example", "parser": "static"}],
        on_failure=failures.append,
    )

    assert notices == []
    assert failures == []


def test_fetch_all_without_a_failure_callback_still_works(monkeypatch):
    monkeypatch.setattr(scraper, "DELAY_BETWEEN_SOURCES_SECONDS", 0)
    monkeypatch.setitem(scraper.PARSERS, "static_html", lambda source: (_ for _ in ()).throw(ValueError("boom")))

    assert scraper.fetch_all([{"name": "x", "url": "https://x.example", "parser": "static_html"}]) == []
