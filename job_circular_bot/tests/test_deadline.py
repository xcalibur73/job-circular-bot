"""Deadline and freshness rules, including Bengali numerals."""

from datetime import date, timedelta

import pytest

from deadline import extract_deadline, filter_expired, is_expired, parse_publication


def _notice(title="Backend Engineer", url="https://example.com/jobs/1", posted_date=None, description=None):
    return {"source": "Example Ltd", "title": title, "url": url,
            "posted_date": posted_date, "description": description}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Apply by 20 October 2026", date(2026, 10, 20)),
        ("Deadline: 20th Oct, 2026", date(2026, 10, 20)),
        ("last date 03-11-2026", date(2026, 11, 3)),
        ("application deadline 2026-10-20", date(2026, 10, 20)),
        ("৩০ December ২০২৬ (Bengali digits, English month)", date(2026, 12, 30)),
    ],
)
def test_deadlines_are_found(text, expected):
    assert extract_deadline(text) == expected


def test_dates_without_a_year_are_ignored():
    assert extract_deadline("apply by 20 October") is None


def test_impossible_dates_are_ignored():
    assert extract_deadline("31 February 2026") is None


def test_no_date_at_all():
    assert extract_deadline("Backend Engineer") is None


def test_expired_is_true_only_for_a_past_deadline():
    today = date(2026, 9, 20)

    past = _notice(title="Urgent hiring, last date 10-09-2026")
    today_exact = _notice(title="Hiring, deadline 20-09-2026")
    future = _notice(title="Hiring, deadline 01-10-2026")
    undated = _notice(title="We are hiring engineers")

    assert is_expired(past, today) == (True, date(2026, 9, 10))
    assert is_expired(today_exact, today) == (False, date(2026, 9, 20))
    assert is_expired(future, today) == (False, date(2026, 10, 1))
    assert is_expired(undated, today) == (False, None)


def test_description_is_searched_when_the_title_has_no_date():
    notice = _notice(title="Graduate Trainee", description="<p>Deadline: 30 November 2025</p>")

    expired, deadline = is_expired(notice, date(2026, 9, 20))

    assert expired is True
    assert deadline == date(2025, 11, 30)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Sun, 16 Jun 2024 17:30:51 +0000", date(2024, 6, 16)),
        ("2026-09-17T13:22:05", date(2026, 9, 17)),
        ("2026-09-17T13:22:05Z", date(2026, 9, 17)),
        ("2026-09-17", date(2026, 9, 17)),
        ("", None),
        ("not a date", None),
        (None, None),
    ],
)
def test_publication_dates_are_parsed(value, expected):
    assert parse_publication(value) == expected


def test_filter_expired_drops_past_deadlines_and_old_listings():
    today = date(2026, 9, 20)

    keep_fresh = _notice(title="Python Developer", posted_date="2026-09-19")
    keep_undated = _notice(title="Python Developer, rolling applications")
    drop_deadlined = _notice(title="Python Developer, last date 01-09-2026")
    drop_stale = _notice(title="Python Developer", posted_date="2026-01-01")

    kept, dropped = filter_expired(
        [keep_fresh, keep_undated, drop_deadlined, drop_stale],
        today=today, max_age_days=60,
    )

    assert kept == [keep_fresh, keep_undated]
    assert [reason for _, reason in dropped] == [
        "application deadline 2026-09-01 already passed",
        "listing is 262 days old",
    ]


def test_no_max_age_means_old_listings_are_kept():
    old = _notice(title="Python Developer", posted_date="2020-01-01")

    kept, dropped = filter_expired([old], today=date(2026, 9, 20), max_age_days=None)

    assert kept == [old]
    assert dropped == []
