# Build Guide: Automated Job Circular Bot for Facebook

This guide walks through building the system you described: a Python script that watches company career pages, and the moment a new hiring notice appears, posts it to your Facebook Page with the original link included for credibility. A working starter code skeleton is included alongside this guide (see the `job_circular_bot` folder or the zip you received with this document).

You told me you want this fully automatic (no manual approval per post), starting with a large list of 10 to 50+ company sites, running on free scheduled cloud runs (GitHub Actions). This guide is written for that setup.

## Read this before you build anything

Two honest flags, as your product advisor rather than just your builder.

**Full automation removes your safety net, not just your workload.** A scraper reading 30+ different websites will occasionally misread one: a title cut off mid-sentence, a stale "we're hiring" banner mistaken for a new post, a link that points to a 404 page after a site redesign. With zero review, those mistakes go straight to your Page under your name. You don't need to add manual approval to fix this. You do need a guardrail layer that catches the obvious garbage before it posts, and an alert that tells you same-day when something looked wrong. That is what `guardrails.py` and `alerting.py` in the starter code do. Treat this as a required part of the build, not an optional extra, even though you're skipping full manual review.

**Scraping company websites has real terms-of-service and legal texture.** Most company career pages don't forbid a human from reading them, but many sites' Terms of Service technically restrict automated scraping, and a few (LinkedIn is the strictest example) actively block and can pursue scrapers. Practical guidance: check each site's `robots.txt` before adding it (a quick visit to `sitename.com/robots.txt` tells you what the site owner says bots may or may not crawl), prefer official feeds or job board APIs over scraping wherever one exists (Bdjobs, some job boards, and some company ATS platforms like Greenhouse or Lever expose RSS or public JSON endpoints), keep your request rate slow and identify your bot honestly in the User-Agent header (already done in the starter code), and never scrape sites that explicitly disallow it in their Terms of Service or robots.txt. This is not a legal opinion, just practical risk reduction. If you plan to scale this commercially or it involves a specific site you're unsure about, that is worth a real legal read, not just my read.

## How the system fits together

```
[company_site_list.txt: the sites you pasted, one URL per line]
            |
            v
   [scraper.py fetches each site]
            |
            v
   [dedup.py drops anything already posted]
            |
            v
   [guardrails.py flags anything that looks broken]
            |                              |
        (looks fine)                 (looks wrong)
            |                              |
            v                              v
 [facebook_poster.py posts it]   [alerting.py pings you on Telegram]
            |
            v
   [dedup.py records it as posted, so it's never posted again]
```

The whole thing runs from `main.py`, on a schedule, with no server to maintain if you use GitHub Actions as planned.

## Step 1: Build your source list, starting small

Even though the target is 10 to 50+ sources, do not add them all on day one. Start with 3 to 5 real career pages you care about, and paste each one into `company_site_list.txt` (repository root), one URL per line. The starter file ships with four reputable remote-job feeds already verified working; add your Bangladeshi employers the same way: paste the URL of the page that actually lists the openings.

You do not write selectors anymore. Each URL is detected automatically:

- a URL ending in `.rss` / `.xml` / `.atom`, or containing `/rss` or `/feed` is read as a feed;
- `remotive.com/api`, `remoteok.com/api` and `jobicy.com/api` are public job APIs, the most reliable option of all;
- everything else is read as a normal page, and the links that look like job postings are picked out for you.

Two things to know:

- Check each site's terms before adding it, and skip any site that forbids automated reading. Prefer feeds and public APIs over scraping wherever one exists.
- Remotive, RemoteOK and Jobicy ask to be credited as the source with a link back. The post template already does exactly that, so leave it in place.

## Step 2: Decide static vs. JS-rendered per site

Most career pages are plain HTML and just work. Some load listings with JavaScript after the page opens (common with Workday, Greenhouse, and many modern company sites), which a plain HTTP request cannot see.

Quick test: run the bot once on the site. If it reports `Found 0 notices`, view the page source (Ctrl+U) and search for one of the job titles you can see on the page. If the title is missing from the source, the site is JS-rendered: add ` |js` to the end of its line in `company_site_list.txt`, and the bot will read it through a real browser instead. You can also force a display name with ` |name=Acme Ltd`.

## Step 2b: Choose your keywords

Run the bot with `--keyword "python, customer support"` (the `run_job_search.bat` file asks you for this), or set standing keywords under `keywords:` in `config/preferences.yaml`. A notice is kept when any term appears in its title, company, tags or category; terms are phrases, separated by commas. `exclude:` drops notices containing any of those terms.

Before anything is posted, the bot also checks that the application window is still open: a notice whose text states a deadline that has already passed is skipped, notices with no stated deadline are kept, and feed listings older than `max_age_days` are dropped as stale.

## Step 3: Set up the Facebook side

This is the part with the most one-time setup. Steps, current as of mid-2026:

1. Go to developers.facebook.com and create an app (type: Business).
2. Make sure the app and your Facebook Page are both inside the same Meta Business Manager account, and that you are an admin of the Page. This matters: as long as you're posting to your own Page from your own Business Manager, you can use Standard Access without going through Meta's full App Review process. App Review is only required if this app will post on behalf of other people's Pages.
3. In the app's dashboard, add the permissions `pages_manage_posts`, `pages_read_engagement`, and `pages_show_list`.
4. Use the Graph API Explorer (developers.facebook.com/tools/explorer), select your app, and generate a User Access Token with those permissions while logged in as the Page admin.
5. Exchange that short-lived user token for a long-lived one (roughly 60 days), then call `/me/accounts` to get your Page Access Token. A Page token derived this way does not expire on its own. It only breaks if you change your Facebook password, remove the app, or lose admin rights on the Page, all rare and all things you'd notice.
6. Store `FB_PAGE_ID` and `FB_PAGE_ACCESS_TOKEN` as GitHub repo secrets. Never commit them into the code.

Meta's permission names and review flow do shift over time, so if anything here doesn't match what you see in the dashboard, treat developers.facebook.com/docs/pages-api as the source of truth over this guide.

## Step 4: Write the post content

The starter code posts each notice as a link post (a `message` plus a `link` field), which makes Facebook auto-generate a preview card for the original notice, exactly the credibility signal you asked for. The default template in `facebook_poster.py`:

```
{Job Title}

{Company Name} has posted a new opening. Full details and how to apply
are in the original notice below. Always double check the deadline and
requirements on the source page before applying.

Apply / read the full notice here: {URL}

#Hiring #Jobs #BangladeshJobs #CareerNotice #{CompanyTag}
```

Adjust the wording to match the voice you want the Page to have. If this Page is meant to feel like a helpful, trustworthy source (the same instinct behind Corporate Daily), keep the tone plain and useful, not salesy, and keep the reminder to double-check the deadline: circulars sometimes get scraped slightly after they've expired, and that one line manages expectations honestly.

## Step 5: Test end to end on one real source

Before turning on the schedule, run the bot locally with just one real site in `company_site_list.txt`. The easy way on Windows is `run_job_search.bat`; on the command line:

```bash
python src/main.py --keyword "your title" --dry-run
```

Confirm:

- The dry run lists the notices it found, filtered by your keyword, with nothing posted to Facebook
- Running it again immediately does NOT post the same notice twice (dedup working)
- Deliberately breaking a URL (typo it) gets caught and alerted, not posted (alerting working)

Only after this passes should you add the rest of your source list, and only then drop the `--dry-run`.

## Step 6: Turn on the schedule

The workflow at the repository root, `.github/workflows/run.yml`, runs the bot every 30 minutes on GitHub Actions, for free, with no server for you to maintain. GitHub Actions runners start empty every time, so the "already posted" database is persisted with `actions/cache` (restored at the start of a run, saved at the end) rather than committed back into the repository - that keeps the history clean and stops two overlapping runs from fighting over a binary file.

Push the project to a GitHub repo, add the four secrets mentioned in Step 3, and the schedule starts. Two GitHub details are worth knowing up front: a fork does not run workflows at all until you enable them in that repository's Actions tab, and a scheduled workflow is switched off automatically after 60 days without any repository activity, so re-enable it if the project goes quiet for a couple of months. You can also trigger a run manually from the Actions tab while testing, and manual runs default to a dry run (fetch and validate, but do not post).

30 minutes is a reasonable starting interval: frequent enough to feel "instant" relative to how often companies actually post circulars, not so frequent that you're hammering 30+ sites every few minutes. You can tighten it later once you've confirmed everything behaves.

## Step 7: Watch it for the first two weeks

Even with guardrails and alerts, the first two weeks are where you'll learn which sites redesign often, which selectors are fragile, and whether the post format actually reads well on the Page. Check the Page daily at first. After that, the Telegram alerts should be enough to tell you when something needs attention.

## The one thing that expires

Meta retires each Graph API version about two years after it is released, and once a version expires every request to it fails - the bot would stop posting with nothing visible on the Page itself. The workflow passes `GRAPH_API_VERSION` as an environment variable and the code reads it, so the fix is to change that single value in `.github/workflows/run.yml` to the current version. The current version and every expiry date are listed at https://developers.facebook.com/docs/graph-api/changelog/versions/. A calendar reminder every three or four months is enough.


## Recommendation

| Factor | Assessment |
|---|---|
| User value | High. Faster access to real circulars is a genuine need for job seekers. |
| Business value | Indirect but real: a fast, credible circular page builds audience and trust, which compounds. |
| Engineering effort | Moderate. The hardest ongoing cost isn't the code, it's maintaining 30-50 site-specific selectors as those sites change. |
| Risk | Real but manageable, mainly ToS/scraping risk per site and occasional bad posts from a broken selector, both addressed above. |
| Time to market | Fast for a 3-5 source pilot (days). Slower to reach 50 sources well, since each one needs individual setup and testing. |

**Build Now**, scoped to a 3-5 source pilot with guardrails and alerts on from day one. **Build Next**: expand toward your full source list once the pilot has run cleanly for two weeks, adding sources a few at a time so any breakage is easy to trace back to the source that caused it.

## What's in the code you received

- `company_site_list.txt`: the sites you watch, one URL per line (you edit this)
- `run_job_search.bat`: double-click launcher; asks for your keyword and dry run or real post
- `config/preferences.yaml`: optional standing keywords, excludes and maximum listing age
- `src/keywords.py`: matches notices against your job titles
- `src/deadline.py`: skips notices whose application deadline has passed, and stale listings
- `src/scraper.py`: fetches listings (public APIs, feeds, plain pages, or a browser for JS sites)
- `src/dedup.py`: remembers what's posted, flagged, and when each source was last polled
- `src/guardrails.py`: catches obviously broken scrapes before they post
- `src/alerting.py`: pings you on Telegram when something needs attention
- `src/facebook_poster.py`: posts to your Page via the Graph API
- `src/main.py`: runs the whole flow, on a schedule or by hand
- `.github/workflows/run.yml`: the free scheduled runner (it has to sit at the repository root, next to this folder, not inside it)
- `README.md`: quick setup checklist
- `tests/`: tests for dedup, the guardrails and the posting path, plus one end-to-end run against a fixture page

This is a working skeleton, not a finished bot. The remaining work is choosing your keywords, adding your sites to company_site_list.txt, and doing the one-time Facebook app setup.
