"""Keyword matching decides what is worth posting, so the rules are explicit."""

import pytest

from keywords import filter_by_keywords, haystack, notice_matches


def _notice(title="Backend Engineer", tags=None, category=None):
    return {"source": "Example Ltd", "title": title, "url": "https://example.com/jobs/1",
            "tags": tags, "category": category}


def test_empty_keywords_match_everything():
    assert notice_matches(_notice(), []) is True


def test_a_keyword_matching_the_title_passes():
    assert notice_matches(_notice(title="Senior Python Developer"), ["python"]) is True


def test_case_does_not_matter():
    assert notice_matches(_notice(title="SENIOR PYTHON DEVELOPER"), ["Python"]) is True


def test_a_non_matching_title_is_dropped():
    assert notice_matches(_notice(title="Accountant"), ["python"]) is False


def test_tags_and_category_are_searched_too():
    assert notice_matches(_notice(title="Engineer", tags=["go", "kubernetes"]), ["kubernetes"]) is True
    assert notice_matches(_notice(title="Engineer", category="Software Development"), ["software"]) is True


def test_phrases_must_match_as_a_whole():
    assert notice_matches(_notice(title="Customer Support Executive"), ["customer support"]) is True
    assert notice_matches(_notice(title="Support Customer Portal"), ["customer support"]) is False


def test_exclude_drops_even_when_keywords_match():
    notice = _notice(title="Python Developer (commission only)")
    assert notice_matches(notice, ["python"], exclude=["commission only"]) is False


def test_exclude_alone_works_without_keywords():
    assert notice_matches(_notice(title="Data Entry Operator"), [], exclude=["data entry"]) is False
    assert notice_matches(_notice(title="Python Developer"), [], exclude=["data entry"]) is True


def test_filter_by_keywords_splits_notices_and_drops_quietly():
    good = _notice(title="Python Developer")
    other = _notice(title="Accountant")

    matching, dropped = filter_by_keywords([good, other], ["python"])

    assert matching == [good]
    assert dropped == [other]


def test_filter_by_keywords_with_no_rules_keeps_everything():
    notices = [_notice(), _notice(title="Accountant")]

    matching, dropped = filter_by_keywords(notices, [])

    assert matching == notices
    assert dropped == []


def test_haystack_includes_source_and_tags():
    notice = {"source": "RemoteOK", "title": "Engineer", "tags": ["django", "api"], "url": "x"}

    assert "django" in haystack(notice)
    assert "remoteok" in haystack(notice)
