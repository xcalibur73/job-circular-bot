"""
Parses company_site_list.txt: the user-facing list of job sources, one per line.

Line format:

  https://example.com/careers                 scraped with generic HTML detection
  https://example.com/feed.xml                RSS is detected automatically
  https://remotive.com/api/remote-jobs        known JSON APIs are detected automatically
  https://example.com/jobs |js                force the headless browser (JS-rendered sites)
  https://example.com/careers |name=Acme Ltd  custom display name

Lines starting with # and blank lines are ignored.
"""

import re
from pathlib import Path
from urllib.parse import urlparse

SITES_PATH = Path(__file__).resolve().parent.parent.parent / "company_site_list.txt"

LINE_RE = re.compile(r"^(?P<url>\S+?)(?:\s+\|(?P<flags>.+))?$")


def parse_site_line(line):
    """Turns one line of the site list into a dict, or None if it is a
    comment, blank, or not a usable URL."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    match = LINE_RE.match(line)
    if not match:
        return None

    url = match.group("url").strip()
    if not url.lower().startswith(("http://", "https://")):
        return None

    name = None
    force_js = False
    for flag in (match.group("flags") or "").split("|"):
        flag = flag.strip()
        if not flag:
            continue
        if flag.lower() == "js":
            force_js = True
        elif flag.lower().startswith("name="):
            name = flag.split("=", 1)[1].strip() or None

    if not name:
        name = urlparse(url).netloc

    return {"url": url, "name": name, "force_js": force_js}


def load_site_lines(path=None):
    """Reads the site list and returns parsed entries.

    A missing or empty file is not an error: the bot simply has nothing to
    check yet, and says so in the log.
    """
    path = Path(path) if path else SITES_PATH
    if not path.exists():
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            parsed = parse_site_line(line)
            if parsed:
                entries.append(parsed)
    return entries
