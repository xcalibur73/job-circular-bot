"""
Fetches job/circular listings from every source in config/sources.yaml.

Each source is checked with one of three strategies:
  - static_html : requests + BeautifulSoup (fast, no browser needed)
  - js_render   : Playwright (a real headless browser, for JS-heavy sites)
  - rss         : feedparser (site already gives you a clean feed, easiest and most reliable)

Returns a flat list of "notice" dicts, one per job/circular found, shaped like:
    {
        "source": "Example Company Ltd",
        "title": "Senior Software Engineer",
        "url": "https://example-company.com/jobs/123",
        "posted_date": "2026-07-20"   # best-effort, may be None
    }

This file is a STARTER. You will fill in real selectors per site in sources.yaml,
and may need small site-specific tweaks over time -- that is normal for scraping
many different websites. Keep each site's quirks in sources.yaml, not in this code,
so adding site #41 doesn't mean touching this file again.
"""

import time
import logging
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobCircularBot/1.0; +https://yourpage.example)"
}
REQUEST_TIMEOUT = 15
DELAY_BETWEEN_SOURCES_SECONDS = 3  # be a polite, slow visitor -- not a hammering bot


def fetch_static_html(source):
    resp = requests.get(source["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    notices = []
    sel = source["selectors"]
    for item in soup.select(sel["list_item"]):
        title_el = item.select_one(sel["title"])
        link_el = item.select_one(sel["link"])
        date_el = item.select_one(sel.get("date", "")) if sel.get("date") else None

        if not title_el or not link_el or not link_el.get("href"):
            continue

        href = link_el["href"]
        if source.get("link_is_relative"):
            href = urljoin(source["url"], href)

        notices.append({
            "source": source["name"],
            "title": title_el.get_text(strip=True),
            "url": href,
            "posted_date": date_el.get_text(strip=True) if date_el else None,
        })
    return notices


def fetch_js_render(source):
    # Only imported here because Playwright is heavier -- keeps static-only setups lightweight.
    from playwright.sync_api import sync_playwright

    sel = source["selectors"]
    notices = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(source["url"], timeout=REQUEST_TIMEOUT * 1000)
        page.wait_for_load_state("networkidle")

        items = page.query_selector_all(sel["list_item"])
        for item in items:
            title_el = item.query_selector(sel["title"])
            link_el = item.query_selector(sel["link"])
            date_el = item.query_selector(sel["date"]) if sel.get("date") else None

            if not title_el or not link_el:
                continue

            href = link_el.get_attribute("href") or ""
            if source.get("link_is_relative"):
                href = urljoin(source["url"], href)

            notices.append({
                "source": source["name"],
                "title": title_el.inner_text().strip(),
                "url": href,
                "posted_date": date_el.inner_text().strip() if date_el else None,
            })
        browser.close()
    return notices


def fetch_rss(source):
    feed = feedparser.parse(source["url"])
    notices = []
    for entry in feed.entries:
        notices.append({
            "source": source["name"],
            "title": entry.get("title", "").strip(),
            "url": entry.get("link"),
            "posted_date": entry.get("published", None),
        })
    return notices


PARSERS = {
    "static_html": fetch_static_html,
    "js_render": fetch_js_render,
    "rss": fetch_rss,
}


def fetch_all(sources):
    """Fetch every source, one at a time, skipping (and logging) any that fail.

    One broken site should never stop the other 40 from being checked.
    """
    all_notices = []
    for source in sources:
        parser_fn = PARSERS.get(source["parser"])
        if not parser_fn:
            logger.warning("Unknown parser '%s' for source '%s', skipping", source["parser"], source["name"])
            continue
        try:
            notices = parser_fn(source)
            logger.info("Fetched %d notice(s) from %s", len(notices), source["name"])
            all_notices.extend(notices)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", source["name"], e)
        time.sleep(DELAY_BETWEEN_SOURCES_SECONDS)
    return all_notices
