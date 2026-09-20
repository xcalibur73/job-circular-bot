"""The posting path is tested without any network access or credentials, using
the DRY_RUN switch."""

import pytest

import facebook_poster as poster

NOTICE = {
    "source": "Example Ltd",
    "title": "Backend Engineer",
    "url": "https://example.com/jobs/1",
}


def test_format_post_contains_the_title_source_and_link():
    text = poster.format_post(NOTICE)

    assert "Backend Engineer" in text
    assert "Example Ltd" in text
    assert "https://example.com/jobs/1" in text
    assert "#ExampleLtd" in text


def test_dry_run_never_calls_facebook(monkeypatch):
    monkeypatch.setattr(poster, "DRY_RUN", True)

    def explode(*args, **kwargs):
        raise AssertionError("a network call was attempted during DRY_RUN")

    monkeypatch.setattr(poster.requests, "post", explode)

    result = poster.post_notice(NOTICE)

    assert result["dry_run"] is True


def test_missing_credentials_raise_a_readable_error(monkeypatch):
    monkeypatch.setattr(poster, "DRY_RUN", False)
    monkeypatch.setattr(poster, "PAGE_ID", None)
    monkeypatch.setattr(poster, "PAGE_ACCESS_TOKEN", None)

    with pytest.raises(RuntimeError) as excinfo:
        poster.post_notice(NOTICE)

    message = str(excinfo.value)
    assert "FB_PAGE_ID" in message
    assert "FB_PAGE_ACCESS_TOKEN" in message
    assert "DRY_RUN" in message
