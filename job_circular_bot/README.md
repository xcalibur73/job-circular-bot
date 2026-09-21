# Job Circular Bot

Watches the job sites you choose and posts every new circular that matches
your keywords to a Facebook Page while the application window is still open.

## How it works

1. You list the sites you care about in `company_site_list.txt` (repository root, one URL per line).
2. You run the bot, or the scheduled GitHub Actions workflow runs it for you.
3. Every new notice that matches your keywords, is still open for application,
   and has not been posted before, goes to the Facebook Page with a link back
   to the original source.

## Quick start (Windows)

Double-click `run_job_search.bat` in the repository root. It asks for:

1. a job title or keyword (press Enter to see everything), and
2. dry run or real post.

On the command line the same thing is:

```bash
cd job_circular_bot
pip install -r requirements.txt
export FB_PAGE_ID="your_page_id"          # PowerShell: $env:FB_PAGE_ID="your_page_id"
export FB_PAGE_ACCESS_TOKEN="your_token"  # PowerShell: $env:FB_PAGE_ACCESS_TOKEN="your_token"
python src/main.py --keyword "python, customer support" --dry-run
```

Drop `--dry-run` when you want a real post. A dry run fetches, filters and
logs what it would have posted, but never calls Facebook and never records
anything, so it cannot spoil a later real run.

## The site list

`company_site_list.txt` holds one URL per line:

```
https://remotive.com/api/remote-jobs        a known public API: no scraping at all
https://example.com/feed.xml                a feed: .rss/.xml/.atom, /rss or /feed
https://www.example.com/careers             a normal page: job-looking links are
                                            picked out automatically
https://www.example.com/jobs |js            a JavaScript-rendered page (uses a browser)
https://www.example.com/careers |name=Acme  custom name on the Facebook Page
```

Four reputable remote-job feeds are already in the file and were verified
working (Remotive, RemoteOK, Jobicy, We Work Remotely). Add your Bangladeshi
employers the same way: paste the URL of the page that actually lists the
openings, and check each site's terms before adding it. Remotive, RemoteOK and
Jobicy ask to be credited as the source with a link back; the post template
already does exactly that, so leave it in place.

If a page produces nothing, it is probably JavaScript-rendered: add ` |js`.

## Keywords and deadlines

- `--keyword "python, django"` (or `keywords:` in `config/preferences.yaml`)
  keeps only notices whose title, company, tags or category contain one of the
  terms. Without keywords, everything the sources return is posted.
- `exclude:` in the same file drops notices containing any of those terms.
- A notice whose text states an application deadline that has already passed
  is skipped. Notices with no stated deadline are kept.
- Feed listings older than `max_age_days` (default 60) are dropped as stale.

Sources also carry their own fair-use limits: Jobicy is polled at most once
per hour and Remotive about four times a day, whichever way you run the bot
with `--respect-intervals` (the scheduled workflow does this for you).

## The scheduled workflow

`.github/workflows/run.yml` runs every 30 minutes. Forks must enable Actions
in the repository's Actions tab first, and GitHub switches scheduled workflows
off automatically after 60 days without repository activity.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

73 tests, no network access and no Facebook credentials. `test_end_to_end.py`
serves a fixture careers page on localhost and runs the whole flow against it,
including the keyword filter and the "never post the same notice twice" check.

## Facebook setup

Create the app and Page Access Token once, as described in the build guide,
then add the secrets to GitHub (Settings -> Secrets and variables -> Actions):
`FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`, and optionally `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` for failure alerts.

See the full build guide document for the reasoning behind each piece and
the Facebook setup steps.

