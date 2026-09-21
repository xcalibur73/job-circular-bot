"""
Fetches job/circular listings from the sites in company_site_list.txt.

You do not configure parsers per site: each URL is detected automatically.

  - json_api  : known public job APIs (Remotive, RemoteOK, Jobicy). The most
                reliable option, because there is no scraping involved at all.
  - rss       : sites that publish a feed (anything ending in .rss, .xml or
                .atom, or containing /rss or /feed in the path).
  - auto_html : everything else. The page is read with requests, and the links
                that look like job postings are picked out.
  - auto_js   : the same link detection, but through a headless browser, for
                sites whose listing only appears after JavaScript runs.
                Select these with the |js marker in company_site_list.txt.

Returns a flat list of "notice" dicts, one per job/circular found, shaped like:

    {
        "source": "Example Ltd",
        "title": "Senior Software Engineer",
        "url": "https://example.com/jobs/123",
        "posted_date": "2026-07-20",   # best-effort, may be None
        "description": "<p>...</p>",   # only when the source provides one
    }

The auto_html and auto_js detectors are best-effort by design: every notice
still passes the guardrails before anything is posted, and a source that
produces nothing is logged and alerted on.
"""

import re
import time
import logging
from urllib.parse import urljoin, urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobCircularBot/1.0; +https://yourpage.example)"
}
REQUEST_TIMEOUT = 15
DELAY_BETWEEN_SOURCES_SECONDS = 3  # be a polite, slow visitor -- not a hammering bot

_session = None


def _get_session():
    """One shared session, with retries for the transient failures that are
    normal when reading 40+ sites in a row (timeouts, brief 5xx responses)."""
    global _session
    if _session is None:
        retry = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        session = requests.Session()
        session.headers.update(HEADERS)
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.mount("http://", HTTPAdapter(max_retries=retry))
        _session = session
    return _session


# Known public job APIs. Their "url" field points at the listing on the
# provider's own site, and every one of them asks to be credited as the
# source -- the Facebook post template does exactly that, so keep it that way.
# min_interval_minutes encodes each provider's fair-use limit.
JSON_API_SOURCES = {
    "remotive.com": {
        "fields": {
            "title": "title",
            "company": "company_name",
            "url": "url",
            "posted_date": "publication_date",
            "tags": "tags",
            "location": "candidate_required_location",
            "description": "description",
        },
        "search_param": "search",
        "min_interval_minutes": 360,   # Remotive asks for at most ~4 pulls a day
    },
    "remoteok.com": {
        "fields": {
            "title": "position",
            "company": "company",
            "url": "url",
            "posted_date": "date",
            "tags": "tags",
            "location": "location",
            "description": "description",
        },
        "min_interval_minutes": 360,
    },
    "jobicy.com": {
        "fields": {
            "title": "jobTitle",
            "company": "companyName",
            "url": "url",
            "posted_date": "pubDate",
            "tags": "jobIndustry",
            "location": "jobGeo",
            "description": "jobDescription",
        },
        "search_param": "tag",
        "min_interval_minutes": 60,    # Jobicy fair use: no more than once per hour
    },
}

FEED_SUFFIXES = (".rss", ".xml", ".atom")

# Links whose target URL mentions one of these fragments are treated as
# possible job postings by the generic detectors.
GENERIC_HREF_HINTS = (
    "job", "career", "vacanc", "recruit", "position", "circular",
    "opening", "hiring", "posting", "employment",
)

# Anchor texts that are navigation, not a job title.
GENERIC_TITLE_STOPWORDS = {
    "home", "about", "about us", "contact", "contact us", "login", "sign in",
    "register", "apply", "apply now", "apply online", "apply here", "read more",
    "click here", "view all", "see more", "more info", "more information",
    "details", "learn more", "jobs", "careers", "job search", "search", "back",
    "next", "previous", "share", "menu", "submit", "join us", "work with us",
    "read the full notice", "view details", "see details", "full details",
    "more details", "job details", "view job", "view posting", "view circular",
    "download circular", "details & apply",
}

GENERIC_TITLE_RE = re.compile(r"[A-Za-z\u0980-\u09FF]")


def detect_source(entry):
    """Turns one parsed line of company_site_list.txt into a source dict."""
    url = entry["url"]
    source = {"url": url, "name": entry["name"]}

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    api = JSON_API_SOURCES.get(host)
    if api and not entry.get("force_js"):
        source["parser"] = "json_api"
        source["fields"] = dict(api["fields"])
        if api.get("search_param"):
            source["search_param"] = api["search_param"]
        source["min_interval_minutes"] = api["min_interval_minutes"]
    elif entry.get("force_js"):
        source["parser"] = "auto_js"
        source["min_interval_minutes"] = 60
    elif (
        parsed.path.lower().endswith(FEED_SUFFIXES)
        or "/rss" in parsed.path.lower()
        or "/feed" in parsed.path.lower()
    ):
        source["parser"] = "rss"
        source["min_interval_minutes"] = 60
    else:
        source["parser"] = "auto_html"
        source["min_interval_minutes"] = 30
    return source


def _notice_from(item, fields, source_name):
    """Maps one JSON API entry onto a notice, or returns None if the entry is
    not a job at all."""
    title = str(item.get(fields["title"]) or "").strip()
    url = item.get(fields["url"])
    if not title or not url:
        return None

    tags = item.get(fields.get("tags")) if fields.get("tags") else None
    if isinstance(tags, (list, tuple)):
        tags = ", ".join(str(tag) for tag in tags)

    def text_field(name):
        if not fields.get(name):
            return None
        value = item.get(fields[name])
        return str(value).strip() if value else None

    return {
        "source": source_name,
        "title": title,
        "url": str(url),
        "posted_date": item.get(fields["posted_date"]) if fields.get("posted_date") else None,
        "company": text_field("company"),
        "location": text_field("location"),
        "tags": tags,
        "description": item.get(fields["description"]) if fields.get("description") else None,
    }


def fetch_json_api(source):
    resp = _get_session().get(source["url"], timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload, dict):
        payload = payload.get("jobs") or []

    notices = []
    for item in payload or []:
        if not isinstance(item, dict):
            continue  # RemoteOK starts its array with a legal notice, not a job
        notice = _notice_from(item, source["fields"], source["name"])
        if notice:
            notices.append(notice)
    return notices


def _looks_like_job_link(href, title):
    """The generic detector's judgement call: does this anchor plausibly point
    at one job posting? False positives still go through the guardrails, and
    false negatives cost the bot one notice, so this stays deliberately
    simple."""
    lower_href = (href or "").lower()
    if not any(hint in lower_href for hint in GENERIC_HREF_HINTS):
        return False

    title = (title or "").strip()
    if not 8 <= len(title) <= 150:
        return False
    if title.lower() in GENERIC_TITLE_STOPWORDS:
        return False
    if not GENERIC_TITLE_RE.search(title):
        return False
    return True


def _notice_from_anchor(href, title, source_name):
    return {
        "source": source_name,
        "title": title,
        "url": href,
        "posted_date": None,
        "description": None,
    }


def fetch_auto_html(source):
    resp = _get_session().get(source["url"], timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    notices, seen = [], set()
    for anchor in soup.find_all("a", href=True):
        title = anchor.get_text(" ", strip=True)
        if not _looks_like_job_link(anchor["href"], title):
            continue
        href = urljoin(source["url"], anchor["href"])
        if href in seen:
            continue
        seen.add(href)
        notices.append(_notice_from_anchor(href, title, source["name"]))

    if not notices:
        logger.info(
            "Found 0 notices on %s. If that looks wrong, the site is probably "
            "JavaScript-rendered: add ' |js' after its line in company_site_list.txt",
            source["name"],
        )
    return notices


def fetch_auto_js(source):
    # Imported here so static-only setups stay lightweight.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(source["url"], timeout=REQUEST_TIMEOUT * 1000)
            page.wait_for_load_state("networkidle")
            # e.href is the resolved, absolute URL of each anchor.
            anchors = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({ href: e.href, text: (e.innerText || e.textContent || '').trim() }))",
            )
        finally:
            # Always release the browser: a slow or broken page would otherwise
            # leak a Chromium process for every failing source.
            browser.close()

    notices, seen = [], set()
    for anchor in anchors:
        href = anchor.get("href") or ""
        title = (anchor.get("text") or "").strip()
        if not _looks_like_job_link(href, title):
            continue
        if href in seen:
            continue
        seen.add(href)
        notices.append(_notice_from_anchor(href, title, source["name"]))

    if not notices:
        logger.info("Found 0 notices on %s through the browser.", source["name"])
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
    "json_api": fetch_json_api,
    "rss": fetch_rss,
    "auto_html": fetch_auto_html,
    "auto_js": fetch_auto_js,
}


def fetch_all(sources, on_failure=None, on_success=None):
    """Fetch every source, one at a time, skipping (and logging) any that fail.

    One broken site should never stop the other 40 from being checked.

    on_failure is called with (source, message) for each source that could
    not be fetched; on_success with the source dict after a successful fetch.
    Pass an alerting function as on_failure so a site that quietly changed its
    layout does not go unnoticed until someone reads the logs.
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
            if on_success:
                on_success(source)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", source["name"], e)
            if on_failure:
                on_failure(source, f"Failed to fetch {source['name']} ({source['url']}): {e}")
        time.sleep(DELAY_BETWEEN_SOURCES_SECONDS)
    return all_notices
