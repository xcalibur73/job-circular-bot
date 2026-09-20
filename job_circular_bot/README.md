# Job Circular Bot

This is a starter skeleton, not a finished product. It gives you the shape of
the system: a config file per source, a scraper that reads that config, a
dedup layer, guardrail checks, and a Facebook poster. You still need to:

1. Fill in real selectors for each company site in `config/sources.yaml`.
2. Create the Facebook App and Page Access Token (see the build guide).
3. Add these secrets to your GitHub repo (Settings -> Secrets and variables -> Actions):
   - `FB_PAGE_ID`
   - `FB_PAGE_ACCESS_TOKEN`
   - `TELEGRAM_BOT_TOKEN` (optional, for failure alerts)
   - `TELEGRAM_CHAT_ID` (optional, for failure alerts)
4. Push this to a GitHub repo. The workflow at the repository root,
   `.github/workflows/run.yml`, runs automatically every 30 minutes.

## Running locally to test

The commands below are run from this folder (`job_circular_bot`), because that
is where `requirements.txt` and `src/` live.

```bash
pip install -r requirements.txt
export FB_PAGE_ID="your_page_id"          # PowerShell: $env:FB_PAGE_ID="your_page_id"
export FB_PAGE_ACCESS_TOKEN="your_token"  # PowerShell: $env:FB_PAGE_ACCESS_TOKEN="your_token"
export DRY_RUN=1                          # fetch and validate, but do not post
python src/main.py
```

Drop `DRY_RUN=1` when you want a real post. In dry run mode the bot fetches,
dedups, runs the guardrails and logs what it would have posted, but it never
calls Facebook and never records anything as posted - so a dry run cannot stop
a later real run from posting the same notice.

Start with `sources.yaml` pointing at just ONE real site, confirm a real
post appears correctly on your Page, then add sources one at a time.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use no network access and no Facebook credentials. `test_end_to_end.py`
serves a fixture careers page from `tests/fixtures/` on localhost and runs the
whole flow against it, including the "do not post the same notice twice" check.

## Sources that need a real browser

Sources with `parser: "js_render"` need Playwright, which lives in its own file
because it downloads a browser:

```bash
pip install -r requirements-browser.txt
python -m playwright install --with-deps chromium
```

See the full build guide document for the reasoning behind each piece and
the Facebook setup steps.

