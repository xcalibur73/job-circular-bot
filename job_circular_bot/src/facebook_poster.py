"""
Posts a job/circular notice to your Facebook Page via the Graph API.

Setup you need to do once (see the build guide for full steps):
  1. Create an app at developers.facebook.com (type: Business).
  2. Add the "Facebook Login for Business" or generate a token via Graph API
     Explorer while logged in as a Page admin.
  3. Request pages_manage_posts, pages_read_engagement, pages_show_list
     (Standard Access is enough as long as your app and Page are in the same
     Business Manager and you are the one posting -- App Review is only
     required once you want other people's pages/users to use this app).
  4. Exchange your short-lived user token for a long-lived one, then fetch
     your Page Access Token from /me/accounts. Long-lived Page tokens do not
     expire unless the password changes, the app is removed, or you lose
     admin rights on the Page.
  5. Put PAGE_ID and PAGE_ACCESS_TOKEN in environment variables / GitHub
     Actions secrets -- never commit them to the repo.
"""

import os
import logging
import requests

logger = logging.getLogger("facebook_poster")

# Meta retires each Graph API version ~2 years after release. v20.0 was released
# 2024-05-21 and expires 2026-09-24, after which every call to it fails:
# https://developers.facebook.com/docs/graph-api/changelog/versions/
# Read from the environment so a future bump is a config change, not a code change.
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v26.0")
PAGE_ID = os.environ.get("FB_PAGE_ID")
PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")

# When DRY_RUN is set, notices are formatted and logged but never sent to
# Facebook. This lets the whole flow be exercised without Page credentials,
# and lets a fork be tested without posting to someone else's Page.
DRY_RUN = os.environ.get("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}

POST_TEMPLATE = """{title}

{source} has posted a new opening. Full details and how to apply are in the original notice below. Always double check the deadline and requirements on the source page before applying.

Apply / read the full notice here: {url}

#Hiring #Jobs #BangladeshJobs #CareerNotice #{source_tag}"""


def format_post(notice):
    source_tag = "".join(ch for ch in notice["source"] if ch.isalnum())
    return POST_TEMPLATE.format(
        title=notice["title"],
        source=notice["source"],
        url=notice["url"],
        source_tag=source_tag,
    )


def post_notice(notice):
    """Publishes one notice to the Page feed as a link post.

    Using the 'link' field (not just raw text) lets Facebook generate a
    clickable preview card for the original notice URL, which is what
    actually drives people to the source and protects credibility.
    """
    message = format_post(notice)

    if DRY_RUN or os.environ.get("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}:
        logger.info("DRY RUN: not posting to Facebook. Would have posted: %s", notice.get("url"))
        return {"id": "dry-run", "dry_run": True}

    missing = [name for name, value in (
        ("FB_PAGE_ID", PAGE_ID),
        ("FB_PAGE_ACCESS_TOKEN", PAGE_ACCESS_TOKEN),
    ) if not value]
    if missing:
        raise RuntimeError(
            "Cannot post to Facebook: missing environment variable(s): "
            + ", ".join(missing)
            + ". Set them in your shell or as GitHub Actions secrets (see README.md), "
            + "or set DRY_RUN=1 to test without posting."
        )

    endpoint = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PAGE_ID}/feed"
    payload = {
        "message": message,
        "link": notice["url"],
        "access_token": PAGE_ACCESS_TOKEN,
    }
    resp = requests.post(endpoint, data=payload, timeout=15)
    if resp.status_code != 200:
        logger.error("Facebook post failed for %s: %s", notice["url"], resp.text)
        resp.raise_for_status()

    result = resp.json()
    logger.info("Posted to Facebook: %s (post id: %s)", notice["title"], result.get("id"))
    return result
