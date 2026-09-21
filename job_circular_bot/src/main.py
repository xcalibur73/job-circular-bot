"""
Orchestrator. Runs on a schedule from GitHub Actions:

    python src/main.py --respect-intervals

or by hand, with the job titles you are looking for:

    python src/main.py --keyword "python, django" --dry-run

Flow:
  1. Read company_site_list.txt: the sites you pasted, one URL per line
  2. Fetch each site, skipping any whose fair-use interval has not elapsed
  3. Keep only the notices matching your keywords, if you gave any
  4. Drop notices whose application deadline has already passed, or that are
     older than the maximum age in preferences
  5. Drop anything already posted before (dedup.py)
  6. Run guardrail sanity checks (guardrails.py); flagged items are skipped
     and alerted on, not posted
  7. Post every remaining, safe, new notice to the Facebook Page
  8. Record what was posted so it is never posted again
  9. Alert you (Telegram) about any source failures or flagged notices
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper import detect_source, fetch_all
from dedup import (
    filter_new,
    mark_posted,
    mark_flagged,
    mark_polled,
    should_poll,
    should_alert_source,
    mark_source_alerted,
)
from guardrails import filter_safe
from keywords import filter_by_keywords
from deadline import filter_expired
from site_list import load_site_lines
from facebook_poster import post_notice
from alerting import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

PREFERENCES_PATH = Path(__file__).resolve().parent.parent / "config" / "preferences.yaml"

# Applied when config/preferences.yaml does not exist or leaves a value out.
PREFERENCE_DEFAULTS = {
    "keywords": [],      # empty = post everything the sources return
    "exclude": [],       # any of these in a notice means it is dropped
    "max_age_days": 60,  # feed listings without deadlines still expire eventually
}


def load_preferences(path=PREFERENCES_PATH):
    """preferences.yaml is optional; the defaults above apply without it."""
    merged = dict(PREFERENCE_DEFAULTS)
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        merged.update({key: value for key, value in loaded.items() if value is not None})
    return merged


def split_terms(text):
    """--keyword 'python, customer support' becomes two phrase terms."""
    if not text:
        return []
    return [term.strip() for term in text.split(",") if term.strip()]


def _add_query_param(url, key, value):
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    query[key] = value
    return urlunparse(parts._replace(query=urlencode(query)))


def build_sources(keyword=None, respect_intervals=True):
    """Turns company_site_list.txt into source dicts.

    The keyword is applied as a server-side search where a source supports
    one, and sources whose fair-use interval has not elapsed are skipped.
    """
    entries = load_site_lines()
    if not entries:
        logger.warning(
            "company_site_list.txt has no sites in it yet. Add one URL per line; "
            "the comments in that file show the format."
        )

    keyword = (keyword or "").strip()
    sources = []
    for entry in entries:
        source = detect_source(entry)
        search_param = source.get("search_param")
        # Server-side search only helps when the term is a single tag-like
        # word; phrases are filtered after fetching instead.
        if keyword and search_param and " " not in keyword:
            source["url"] = _add_query_param(source["url"], search_param, keyword)
        sources.append(source)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    eligible = []
    for source in sources:
        minutes = source.get("min_interval_minutes", 0)
        if respect_intervals and minutes and not should_poll(source["url"], minutes, now):
            logger.info(
                "Skipping %s for this run: polled less than %d minute(s) ago",
                source["name"], minutes,
            )
            continue
        eligible.append(source)
    return eligible


def run(keyword=None, respect_intervals=True, preferences=None):
    prefs = preferences or load_preferences()
    terms = split_terms(keyword) or prefs["keywords"]
    exclude = prefs["exclude"]
    max_age_days = prefs.get("max_age_days")

    if terms:
        logger.info("Looking for: %s", ", ".join(terms))
    sources = build_sources(keyword, respect_intervals)
    logger.info("Checking %d source(s)...", len(sources))

    # A failed source is reported through the same channel as everything else;
    # on a scheduled cloud run nobody reads the console log. A source that
    # stays broken must not ring the bell every 30 minutes, though, so it is
    # reminded at most once a day until it is fixed.
    def report_failure(source, message):
        if should_alert_source(source["url"]):
            send_alert(message)
            mark_source_alerted(source["url"])

    all_notices = fetch_all(
        sources,
        on_failure=report_failure,
        on_success=lambda source: mark_polled(source["url"]),
    )

    matching, dropped = filter_by_keywords(all_notices, terms, exclude)
    logger.info(
        "%d notice(s) match the keyword filter, %d dropped as unrelated",
        len(matching), len(dropped),
    )

    fresh, expired = filter_expired(matching, max_age_days=max_age_days)
    for notice, reason in expired:
        # Logged, not alerted: a feed full of stale listings would otherwise
        # ring the Telegram bell on every run.
        logger.info("Skipping %s: %s", notice.get("url"), reason)
    logger.info("%d notice(s) still open for application", len(fresh))

    new_notices = filter_new(fresh)
    logger.info("%d new notice(s) out of %d still open", len(new_notices), len(fresh))

    safe_notices, flagged = filter_safe(new_notices)

    for notice, reason in flagged:
        send_alert(f"Flagged and skipped a notice from {notice.get('source')}: {reason}\n{notice.get('url')}")
        # Record it so the same listing is not alerted on again every 30 minutes.
        mark_flagged(notice, reason)

    posted_count = 0
    for notice in safe_notices:
        try:
            result = post_notice(notice)
            if result.get("dry_run"):
                logger.info("DRY RUN: would have posted %s", notice.get("url"))
                continue
            mark_posted(notice)
            posted_count += 1
        except Exception as e:
            logger.error("Failed to post notice %s: %s", notice.get("url"), e)
            send_alert(f"Failed to post a notice from {notice.get('source')}: {e}\n{notice.get('url')}")

    logger.info("Done. Posted %d new notice(s).", posted_count)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Post new job circulars from company_site_list.txt to the Facebook Page.",
    )
    parser.add_argument(
        "--keyword",
        help="comma-separated job title terms to look for, e.g. --keyword 'python, django'. "
        "Without it, keywords from config/preferences.yaml apply (or every notice is posted).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="fetch, filter and log, but do not post anything to Facebook",
    )
    parser.add_argument(
        "--respect-intervals", action="store_true",
        help="skip sources whose fair-use interval has not elapsed yet (the scheduled workflow uses this)",
    )
    parser.add_argument(
        "--list-sources", action="store_true",
        help="show how each line of company_site_list.txt was detected, then exit",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.list_sources:
        for entry in load_site_lines():
            source = detect_source(entry)
            print(f"{source['parser']:10} {source['name']:30} {source['url']}")
        return 0

    if args.dry_run:
        os.environ["DRY_RUN"] = "1"

    run(keyword=args.keyword, respect_intervals=args.respect_intervals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
