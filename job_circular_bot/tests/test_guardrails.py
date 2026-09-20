"""Guardrails decide what is allowed onto the Page, so every branch is checked
explicitly."""

import pytest

from guardrails import filter_safe, is_safe_to_post


def _notice(title="Backend Engineer", url="https://example.com/jobs/1"):
    return {"source": "Example Ltd", "title": title, "url": url}


def test_a_plain_looking_notice_is_safe():
    safe, reason = is_safe_to_post(_notice())

    assert safe is True
    assert reason == ""


@pytest.mark.parametrize(
    "notice",
    [
        pytest.param(_notice(title=""), id="empty title"),
        pytest.param(_notice(title="     "), id="whitespace-only title"),
        pytest.param(_notice(title="Job"), id="title below the minimum length"),
        pytest.param(_notice(title="x" * 201), id="title above the maximum length"),
        pytest.param(_notice(title="undefined"), id="scraper artifact: undefined"),
        pytest.param(_notice(title="UNDEFINED section heading"), id="scraper artifact, any case"),
        pytest.param(_notice(title="Page not found"), id="error page scraped as a listing"),
        pytest.param(_notice(url=None), id="missing url"),
        pytest.param(_notice(url=""), id="empty url"),
        pytest.param(_notice(url="ftp://example.com/jobs/1"), id="non-http url"),
    ],
)
def test_suspicious_notices_are_rejected(notice):
    safe, reason = is_safe_to_post(notice)

    assert safe is False
    assert reason


def test_filter_safe_splits_notices_and_keeps_the_reason():
    good = _notice()
    bad = _notice(title="")

    safe, flagged = filter_safe([good, bad])

    assert safe == [good]
    assert len(flagged) == 1
    assert flagged[0][0] == bad
    assert "title length looks wrong" in flagged[0][1]
