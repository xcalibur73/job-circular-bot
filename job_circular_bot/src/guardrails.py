"""
Lightweight sanity checks that run BEFORE a notice is posted, even in
fully-automatic mode. These catch the most common ways a scraper goes wrong
without slowing anything down or requiring a human to approve each post.

This is not "manual review" -- it's the automated equivalent of a second
pair of eyes, so a broken selector or a stale page doesn't turn into a bad
post on the Facebook Page.
"""

import re
import logging

logger = logging.getLogger("guardrails")

MIN_TITLE_LENGTH = 5
MAX_TITLE_LENGTH = 200
SUSPICIOUS_PATTERNS = [
    re.compile(r"^\s*$"),           # empty/whitespace-only title
    re.compile(r"undefined", re.I),  # common scraper artifact
    re.compile(r"page not found", re.I),
]


def is_safe_to_post(notice):
    """Returns (True, "") if the notice looks legit, or (False, reason) if not."""
    title = notice.get("title", "")
    url = notice.get("url", "")

    if not url or not url.startswith("http"):
        return False, "missing or invalid URL"

    if len(title) < MIN_TITLE_LENGTH or len(title) > MAX_TITLE_LENGTH:
        return False, f"title length looks wrong ({len(title)} chars)"

    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(title):
            return False, f"title matched suspicious pattern: {pattern.pattern}"

    return True, ""


def filter_safe(notices):
    """Splits notices into (safe_to_post, flagged) so flagged ones can be logged
    and alerted on instead of silently posted or silently dropped."""
    safe, flagged = [], []
    for notice in notices:
        ok, reason = is_safe_to_post(notice)
        if ok:
            safe.append(notice)
        else:
            logger.warning("Flagged notice from %s: %s (%s)", notice.get("source"), reason, notice.get("url"))
            flagged.append((notice, reason))
    return safe, flagged
