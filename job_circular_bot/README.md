# Job Circular Bot (starter)

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
4. Push this to a GitHub repo. The workflow in `.github/workflows/run.yml`
   runs automatically every 30 minutes.

## Running locally to test

```bash
pip install -r requirements.txt
export FB_PAGE_ID="your_page_id"
export FB_PAGE_ACCESS_TOKEN="your_token"
python src/main.py
```

Start with `sources.yaml` pointing at just ONE real site, confirm a real
post appears correctly on your Page, then add sources one at a time.

See the full build guide document for the reasoning behind each piece and
the Facebook setup steps.
