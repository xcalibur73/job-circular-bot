"""
Keyword matching between the job titles the user asked for and fetched notices.

Rules:
  - keywords: at least one term must appear (case-insensitive) in the notice
    title, company, tags or category. An empty list means every notice passes.
  - exclude: if any term appears, the notice is dropped.
  - terms are whole phrases: "customer support" only matches that phrase, and
    terms are separated by commas, so --keyword "python, customer support"
    looks for either.

Notices dropped here are not remembered anywhere, so running again later with
different keywords still sees them.
"""

import logging

logger = logging.getLogger("keywords")


def haystack(notice):
    """Everything a keyword could plausibly match in one lowercase string."""
    parts = [notice.get("title", ""), notice.get("source", "")]
    tags = notice.get("tags")
    if isinstance(tags, (list, tuple)):
        parts.extend(str(tag) for tag in tags)
    elif tags:
        parts.append(str(tags))
    if notice.get("category"):
        parts.append(str(notice["category"]))
    return " ".join(part for part in parts if part).lower()


def notice_matches(notice, keywords, exclude=None):
    """True when the notice passes the keyword rules."""
    hay = haystack(notice)

    for term in exclude or []:
        if term.lower().strip() and term.lower() in hay:
            return False

    if not keywords:
        return True
    return any(term.lower().strip() and term.lower() in hay for term in keywords)


def filter_by_keywords(notices, keywords, exclude=None):
    """Splits notices into (matching, dropped).

    Dropped notices are removed from this run but remembered nowhere: a later
    run with other keywords still sees them.
    """
    if not keywords and not exclude:
        return list(notices), []

    matching, dropped = [], []
    for notice in notices:
        if notice_matches(notice, keywords, exclude):
            matching.append(notice)
        else:
            dropped.append(notice)
    return matching, dropped
