# Build Guide: Automated Job Circular Bot for Facebook

This guide walks through building the system you described: a Python script that watches company career pages, and the moment a new hiring notice appears, posts it to your Facebook Page with the original link included for credibility. A working starter code skeleton is included alongside this guide (see the `job_circular_bot` folder or the zip you received with this document).

You told me you want this fully automatic (no manual approval per post), starting with a large list of 10 to 50+ company sites, running on free scheduled cloud runs (GitHub Actions). This guide is written for that setup.

## Read this before you build anything

Two honest flags, as your product advisor rather than just your builder.

**Full automation removes your safety net, not just your workload.** A scraper reading 30+ different websites will occasionally misread one: a title cut off mid-sentence, a stale "we're hiring" banner mistaken for a new post, a link that points to a 404 page after a site redesign. With zero review, those mistakes go straight to your Page under your name. You don't need to add manual approval to fix this. You do need a guardrail layer that catches the obvious garbage before it posts, and an alert that tells you same-day when something looked wrong. That is what `guardrails.py` and `alerting.py` in the starter code do. Treat this as a required part of the build, not an optional extra, even though you're skipping full manual review.

**Scraping company websites has real terms-of-service and legal texture.** Most company career pages don't forbid a human from reading them, but many sites' Terms of Service technically restrict automated scraping, and a few (LinkedIn is the strictest example) actively block and can pursue scrapers. Practical guidance: check each site's `robots.txt` before adding it (a quick visit to `sitename.com/robots.txt` tells you what the site owner says bots may or may not crawl), prefer official feeds or job board APIs over scraping wherever one exists (Bdjobs, some job boards, and some company ATS platforms like Greenhouse or Lever expose RSS or public JSON endpoints), keep your request rate slow and identify your bot honestly in the User-Agent header (already done in the starter code), and never scrape sites that explicitly disallow it in their Terms of Service or robots.txt. This is not a legal opinion, just practical risk reduction. If you plan to scale this commercially or it involves a specific site you're unsure about, that is worth a real legal read, not just my read.

## How the system fits together

```
[sources.yaml: list of company sites]
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

Even though the target is 10 to 50+ sources, do not add them all on day one. Start with 3 to 5 real company career pages you care about. For each one, open the page, right-click on a job listing, choose Inspect, and note:

- What HTML element wraps one job listing (a `div`, `li`, or similar, repeated for each job)
- What element holds the job title
- What element holds the link to the full notice
- Whether that link is a full URL or a relative path like `/jobs/123`

Put these into `config/sources.yaml` (the starter file has two worked examples plus an RSS example). This config-driven approach is exactly why the plan to reach 50+ sources will not turn into a mess of duplicated code: adding company #41 means adding a new block to `sources.yaml`, not writing new code.

A few sites will already publish an RSS or Atom feed of jobs (check for a `/feed` or `/rss` URL, or search "[company name] careers rss"). Always prefer that over scraping HTML: it's more stable, lighter on their server, and less likely to break when they redesign their site.

## Step 2: Decide static vs. JS-rendered per site

Some career pages are plain HTML (the job listings are in the page source you can view with "View Page Source"). Others load listings with JavaScript after the page opens (common with Workday, Greenhouse, and many modern company sites), which means a simple HTTP request won't see the job list at all.

Quick test: open the page, view source (Ctrl+U or Cmd+Option+U), and search for one of the job titles you can see on the page. If it's there, mark that source `static_html` in the config (fast, uses `requests` and `BeautifulSoup`). If it's not there, mark it `js_render` (uses Playwright, a real headless browser, slower but works on JS-heavy sites).

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

Before turning on the schedule, run `python src/main.py` locally against a `sources.yaml` with just one real source in it. Confirm:

- A real post appears on your Page with the right title, link, and preview card
- Running it again immediately does NOT post the same notice twice (dedup working)
- Deliberately breaking a selector (typo it) gets caught and alerted, not posted (guardrails working)

Only after this passes should you add the rest of your source list.

## Step 6: Turn on the schedule

The included `.github/workflows/run.yml` runs the bot every 30 minutes on GitHub Actions, for free, with no server for you to maintain. It also commits the "already posted" database back to the repo after each run, since GitHub Actions doesn't keep files between runs otherwise.

Push the project to a GitHub repo, add the four secrets mentioned in Step 3, and the schedule starts automatically. You can also trigger a run manually from the repo's Actions tab while testing.

30 minutes is a reasonable starting interval: frequent enough to feel "instant" relative to how often companies actually post circulars, not so frequent that you're hammering 30+ sites every few minutes. You can tighten it later once you've confirmed everything behaves.

## Step 7: Watch it for the first two weeks

Even with guardrails and alerts, the first two weeks are where you'll learn which sites redesign often, which selectors are fragile, and whether the post format actually reads well on the Page. Check the Page daily at first. After that, the Telegram alerts should be enough to tell you when something needs attention.

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

- `config/sources.yaml`: your list of sites and how to read each one
- `src/scraper.py`: fetches listings (static HTML, JS-rendered, or RSS)
- `src/dedup.py`: remembers what's already been posted
- `src/guardrails.py`: catches obviously broken scrapes before they post
- `src/alerting.py`: pings you on Telegram when something needs attention
- `src/facebook_poster.py`: posts to your Page via the Graph API
- `src/main.py`: runs the whole flow, meant to be scheduled
- `.github/workflows/run.yml`: the free scheduled runner
- `README.md`: quick setup checklist

This is a working skeleton, not a finished bot. The remaining work is filling in real selectors for your actual source list and doing the one-time Facebook app setup.
