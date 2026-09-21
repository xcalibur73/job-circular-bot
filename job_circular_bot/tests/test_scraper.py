"""A failing source must be reported, not just logged, and must never stop the
remaining sources from being checked. URL detection and the JSON APIs are
covered here too."""

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
    monkeypatch.setitem(scraper.PARSERS, "auto_html", explode)
    monkeypatch.setitem(scraper.PARSERS, "rss", lambda source: working)

    failures = []
    successes = []
    notices = scraper.fetch_all(
        [
            {"name": "Broken Ltd", "url": "https://broken.example/careers", "parser": "auto_html"},
            {"name": "Working Ltd", "url": "https://working.example/feed.xml", "parser": "rss"},
        ],
        on_failure=lambda source, message: failures.append((source, message)),
        on_success=lambda source: successes.append(source["name"]),
    )

    assert notices == working
    assert len(failures) == 1
    assert failures[0][0]["name"] == "Broken Ltd"
    assert "Broken Ltd" in failures[0][1]
    assert "site changed its layout" in failures[0][1]
    assert successes == ["Working Ltd"]


def test_unknown_parser_is_skipped_without_reporting_a_failure(monkeypatch):
    monkeypatch.setattr(scraper, "DELAY_BETWEEN_SOURCES_SECONDS", 0)

    failures = []
    notices = scraper.fetch_all(
        [{"name": "Typo Ltd", "url": "https://typo.example", "parser": "static"}],
        on_failure=failures.append,
    )

    assert notices == []
    assert failures == []


def test_detect_source_recognises_known_json_apis():
    source = scraper.detect_source({"url": "https://www.remotive.com/api/remote-jobs", "name": "r", "force_js": False})

    assert source["parser"] == "json_api"
    assert source["fields"]["title"] == "title"
    assert source["min_interval_minutes"] == 360


def test_detect_source_recognises_feeds_by_suffix_and_path():
    for url in (
        "https://example.com/jobs.rss",
        "https://example.com/feed.xml",
        "https://example.com/blog/feed",
        "https://example.com/rss/jobs",
    ):
        assert scraper.detect_source({"url": url, "name": "x", "force_js": False})["parser"] == "rss"


def test_detect_source_defaults_to_generic_html_and_respects_the_js_flag():
    html = scraper.detect_source({"url": "https://example.com/careers", "name": "x", "force_js": False})
    forced = scraper.detect_source({"url": "https://example.com/careers", "name": "x", "force_js": True})

    assert html["parser"] == "auto_html"
    assert html["min_interval_minutes"] == 30
    assert forced["parser"] == "auto_js"


def test_fetch_json_api_maps_fields_and_skips_non_jobs(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "jobs": [
                    {
                        "jobTitle": "Backend Engineer",
                        "companyName": "Example Ltd",
                        "url": "https://example.com/jobs/1",
                        "pubDate": "2026-09-19T10:00:00+00:00",
                        "jobIndustry": ["Software", "QA"],
                        "jobGeo": "Anywhere",
                        "jobDescription": "<p>apply</p>",
                    },
                    {"jobTitle": "", "url": "https://example.com/nope"},   # no title: skipped
                    "not a dict",                                          # skipped
                ]
            }

    class FakeSession:
        def get(self, url, timeout=None):
            return FakeResponse()

    monkeypatch.setattr(scraper, "_get_session", lambda: FakeSession())

    source = scraper.detect_source({"url": "https://jobicy.com/api/v2/remote-jobs", "name": "Jobicy", "force_js": False})
    notices = scraper.fetch_json_api(source)

    assert len(notices) == 1
    notice = notices[0]
    assert notice["title"] == "Backend Engineer"
    assert notice["company"] == "Example Ltd"
    assert notice["tags"] == "Software, QA"
    assert notice["posted_date"] == "2026-09-19T10:00:00+00:00"


def test_fetch_auto_html_picks_job_links_and_skips_navigation(monkeypatch):
    html = """
    <html><body>
      <a href="/jobs/1">Backend Engineer at Example Ltd</a>
      <a href="/jobs/2">Data Analyst position open</a>
      <a href="/jobs/2">Data Analyst position open</a>
      <a href="/careers/apply">Read the full notice</a>
      <a href="/about">About us</a>
      <a href="/jobs/3">x</a>
    </body></html>
    """

    class FakeResponse:
        status_code = 200
        text = html

        def raise_for_status(self):
            pass

    class FakeSession:
        def get(self, url, timeout=None):
            return FakeResponse()

    monkeypatch.setattr(scraper, "_get_session", lambda: FakeSession())

    notices = scraper.fetch_auto_html({"url": "https://example.com/careers", "name": "Example Ltd"})

    assert [(n["title"], n["url"]) for n in notices] == [
        ("Backend Engineer at Example Ltd", "https://example.com/jobs/1"),
        ("Data Analyst position open", "https://example.com/jobs/2"),
    ]
