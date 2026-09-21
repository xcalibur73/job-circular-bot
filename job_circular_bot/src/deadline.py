"""
Application-deadline handling.

A notice is only worth posting while candidates can still apply:

  - if a deadline is stated and is in the past, the notice is skipped;
  - if no deadline can be found, the notice is kept (no stated limit);
  - for feeds that publish a listing date, an optional maximum age
    (max_age_days in preferences) drops very old listings.

Bengali circulars often write dates with Bengali numerals, so those are
converted before parsing. Only full dates (day + month + year) count; partial
dates are ignored rather than guessed. Dates without a year are also ignored,
since they cannot be compared against the search time.
"""

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime

BENGALI_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

MONTH_NAME_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\.?,?\s+(\d{4})\b",
    re.IGNORECASE,
)
ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
NUMERIC_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")

HTML_RE = re.compile(r"<[^>]+>")


def extract_deadline(text):
    """Best-effort deadline extraction from free text. Returns a date or None.

    Numeric dates are read day-first (the convention in Bangladesh circulars);
    ISO dates (2026-10-20) are unambiguous and are tried first.
    """
    if not text:
        return None

    text = str(text).translate(BENGALI_DIGITS)

    match = ISO_RE.search(text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    match = MONTH_NAME_RE.search(text)
    if match:
        day = int(match.group(1))
        month = _MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            pass

    match = NUMERIC_RE.search(text)
    if match:
        day, month, year = (int(match.group(i)) for i in (1, 2, 3))
        try:
            return date(year, month, day)
        except ValueError:
            pass

    return None


def parse_publication(value):
    """Parses a listing/publication date from a feed or API. date or None."""
    if not value:
        return None

    value = str(value).strip().translate(BENGALI_DIGITS)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        pass

    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def is_expired(notice, today=None):
    """Returns (expired, deadline).

    expired is True only when a stated deadline is strictly in the past: a
    deadline of today can still be applied to. Notices with no stated
    deadline are never considered expired.
    """
    today = today or date.today()

    for field in ("title", "description"):
        value = notice.get(field)
        if not value:
            continue
        text = HTML_RE.sub(" ", str(value)) if field == "description" else str(value)
        deadline = extract_deadline(text)
        if deadline:
            return deadline < today, deadline

    return False, None


def filter_expired(notices, today=None, max_age_days=None):
    """Splits notices into (kept, dropped).

    Dropped notices carry a reason: a passed deadline, or a listing older
    than max_age_days (only applies when the source publishes a date).
    """
    today = today or date.today()
    kept, dropped = [], []

    for notice in notices:
        expired, deadline = is_expired(notice, today)
        if expired:
            dropped.append((notice, f"application deadline {deadline.isoformat()} already passed"))
            continue

        published = parse_publication(notice.get("posted_date"))
        if max_age_days and published:
            age_days = (today - published).days
            if age_days > max_age_days:
                dropped.append((notice, f"listing is {age_days} days old"))
                continue

        kept.append(notice)

    return kept, dropped
