"""
Orchestrator: run this on a schedule (e.g. every 20-30 minutes via GitHub Actions).

Flow:
  1. Fetch listings from every source in config/sources.yaml
  2. Drop anything already posted before (dedup.py)
  3. Run guardrail sanity checks (guardrails.py) -- flagged items are skipped
     and alerted on, not posted
  4. Post every remaining, safe, new notice to the Facebook Page
  5. Record what was posted so it's never posted again
  6. Alert you (Telegram) about any source failures or flagged notices
"""

import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper import fetch_all
from dedup import filter_new, mark_posted, mark_flagged
from guardrails import filter_safe
from facebook_poster import post_notice
from alerting import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"


def load_sources():
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config["sources"]


def run():
    sources = load_sources()
    logger.info("Checking %d source(s)...", len(sources))

    # A failed source is reported through the same channel as everything else;
    # on a scheduled cloud run nobody reads the console log.
    all_notices = fetch_all(sources, on_failure=send_alert)
    new_notices = filter_new(all_notices)
    logger.info("%d new notice(s) out of %d fetched", len(new_notices), len(all_notices))

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


if __name__ == "__main__":
    run()
