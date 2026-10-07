# Bothsiders — daily automated news issue

Fully automated pipeline: every day, a script researches the day's top
stories with Claude, writes structured content, renders it into the
Bothsiders template, and publishes it — no human step required. Every
day's issue is kept forever and browsable from a Library page grouped by
month.

## How it works

1. **`generate_content.py`** calls the Claude API with the web search tool
   enabled. It researches real news and returns structured JSON (not raw
   HTML) — one object per story, following the category/axis rules baked
   into its prompt.
2. **`render.py`** takes that JSON and:
   - writes today's issue to `issues/YYYY-MM-DD.html` (kept permanently),
   - overwrites `index.html` with the same content (the homepage always
     shows the latest issue),
   - updates `manifest.json` (the running list of every issue published),
   - rebuilds `library.html` from that manifest, grouped by month.
3. **`templates/issue.html`** and **`templates/library.html`** are the only
   places page structure lives; **`assets/style.css`** is the only place
   visual design lives. The generation scripts only ever fill in
   placeholders, so the site's look can't drift day to day.
4. **`assets/logo-full.png`** (the full lockup) and **`assets/logo-mark.png`**
   (the icon alone, also used as the favicon) are the only graphic on the
   site — everything else is typography and flat color.
5. **`.github/workflows/daily.yml`** runs the pipeline on a schedule via
   GitHub Actions, commits everything that changed, and pushes it. GitHub
   Pages (once enabled) redeploys automatically on every push to `main`.

## Site structure once deployed

```
index.html          → always the latest issue (the homepage)
library.html         → every issue, grouped by month
issues/2026-09-25.html, issues/2026-09-26.html, ...  → permanent per-day archive
manifest.json         → plain-text record of every published date
assets/               → logo files + the one shared stylesheet
config.py              → the values you set once (site URL, Buttondown username, contact email, governing state)
privacy-policy.html, terms.html → static legal pages, linked from every page's footer
```

## Privacy Policy and Terms & Conditions

Two static pages — `privacy-policy.html` and `terms.html` — are linked from
the footer of every page on the site. They're generated once (not part of
the daily job, since legal text doesn't change based on the day's news) by
`generate_legal_pages.py`, which fills in `templates/privacy.html` and
`templates/terms.html` with the values from `config.py`.

**Before you publish these, please read this carefully:** I drafted this
Privacy Policy and these Terms to be a solid, genuinely useful starting
point — covering the specific things this site actually does (the
Buttondown newsletter, GitHub Pages hosting, no accounts or payments, an
AI-assisted content disclaimer given how the site is produced) — but I'm
not a lawyer, this isn't legal advice, and I can't guarantee these
documents satisfy every law that might apply to you. Have an actual
attorney review both pages before you rely on them, especially given:
- You're collecting email addresses, which brings in laws like CAN-SPAM
  (US) and potentially GDPR/CCPA depending on who subscribes and where
  you/they are located;
- The site publishes AI-assisted commentary on political topics, where
  defamation and editorial-disclosure norms matter more than on a typical
  hobby site;
- State-specific requirements (some states, like California, have specific
  rules about what a privacy policy must disclose) aren't something I can
  fully verify are met without knowing your exact setup.

### One-time setup for the legal pages

1. **Fill in `config.py`**: `CONTACT_EMAIL` (a real inbox you check) and
   `GOVERNING_LAW_STATE` (defaults to California, matching where you're
   based — change it if you'd rather use another state).
2. **Run the generator**: `python generate_legal_pages.py` — writes
   `privacy-policy.html` and `terms.html` at the repo root, dated with
   today's date.
3. **Have both pages reviewed** before the site goes live, per the note
   above.
4. **Re-run the generator** any time you actually edit the policy text in
   `templates/privacy.html` / `templates/terms.html`, or change your
   contact email — it overwrites the two output files with a fresh "Last
   updated" date.

## Email signup and sending

The site can't collect or send email on its own (GitHub Pages is static,
no backend), so this uses **Buttondown** — a newsletter service — for both
halves of the job:

- **Collecting signups**: every page has a signup box that posts straight
  to Buttondown's hosted subscribe endpoint. No server of yours is
  involved; Buttondown stores the list, handles unsubscribes, and is
  CAN-SPAM compliant out of the box.
- **Sending daily**: `send_email.py` reads the same `content.json`
  `render.py` uses and builds a branded HTML email — logo, brand colors,
  the same category badges as the site — using inline styles on every
  element rather than the site's actual CSS (email clients, Outlook
  especially, don't support flexbox, grid, CSS variables, or `<style>`
  blocks reliably; inline styles are what actually survives across inboxes).
  The logo is a normal hosted `<img>` pointing at the live site's own
  `assets/` files, not an embedded image — inline/base64 images get
  stripped by most mail clients. The script then calls Buttondown's API to
  send it to everyone on the list, and each story still links back to the
  full page on the web.

### One-time setup for email

1. **Create a Buttondown account** at buttondown.email and note your
   username (the part after `buttondown.email/` in your newsletter's URL).
2. **Set it in `config.py`**: put that username in `BUTTONDOWN_USERNAME`,
   and your real site URL in `SITE_BASE_URL` once you know it (step 4
   below) — this is the only file you need to touch for either value.
3. **Get your Buttondown API key** from your Buttondown settings, and add
   it as a repo secret named `BUTTONDOWN_API_KEY` (same place you added
   `ANTHROPIC_API_KEY`).
4. **Verify two things before your first real send.** I built
   `send_email.py` from Buttondown's documented API, but double-check
   these against Buttondown's current reference before relying on them —
   getting either wrong could mean nothing sends, or an email goes out to
   your whole list before you're ready:
   - **The `status` field** that triggers an immediate send (the script
     uses `"about_to_send"` — confirm that's still correct).
   - **That the `body` field accepts raw HTML.** The email template is
     now full HTML (logo, colors, badges), not the plain Markdown from an
     earlier version of this script. Most Markdown processors pass raw
     HTML through untouched, which is what this relies on — but if
     Buttondown escapes or strips it instead, the email will show broken
     tags instead of a rendered layout. Test with `"status": "draft"`
     first (creates the email in your Buttondown dashboard without
     sending it) and open the draft to confirm the logo and colors
     actually render before switching to the sending value.
   - Note also that the logo images in the email are hosted links to your
     live site (`SITE_BASE_URL/assets/...`), so they won't load in a
     preview until the site is actually deployed and `SITE_BASE_URL` in
     `config.py` points at the real URL.

That's the only manual verification step in the whole pipeline — everything
else here has been tested end to end.

## One-time setup

1. **Create a GitHub repo** and push these files to it (`main` branch).

2. **Get an Anthropic API key** at console.anthropic.com if you don't
   already have one, and add a small amount of credit — this pipeline
   costs roughly a few cents per day in API usage (web search is billed
   per search; text generation is billed per token).

3. **Add the key as a repo secret**:
   Repo → Settings → Secrets and variables → Actions → New repository
   secret → name it `ANTHROPIC_API_KEY`, paste your key.

4. **Enable GitHub Pages**:
   Repo → Settings → Pages → Source: "Deploy from a branch" → Branch:
   `main` / root. GitHub will give you a URL like
   `https://yourusername.github.io/bothsiders/`.

5. **(Optional) Custom domain** — Settings → Pages → add your domain
   (e.g. `bothsiders.news`) and point its DNS at GitHub Pages per
   GitHub's instructions. Free, just needs a domain you own.

6. **Test it manually first**: Actions tab → "Generate daily Bothsiders
   issue" → "Run workflow" → watch it run once before trusting the cron
   schedule. Open the resulting `index.html` and `library.html` and check
   they look right before letting it run unattended.

That's it — after this, the workflow fires daily on its own schedule
(edit the cron line in `daily.yml` to change the time) and the live site
updates itself every morning, with the Library filling in one date at a
time.

## Running it locally (to test or tweak before deploying)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export BUTTONDOWN_API_KEY=...
python generate_content.py   # writes content.json
python render.py             # writes index.html, issues/<date>.html, library.html
python send_email.py         # sends (or drafts, per the status you set) today's email
open index.html              # preview in your browser
```

Running `render.py` again with a new `content.json` (a new date) adds to
the archive rather than replacing it — `manifest.json` and `library.html`
accumulate, they never get overwritten.

## Tuning it

- **Number of stories**: change `NUM_STORIES` in `generate_content.py`.
- **Timezone / dateline**: change `TIMEZONE` in `generate_content.py`.
- **Run time**: edit the `cron` line in `.github/workflows/daily.yml`
  (cron times are in UTC).
- **Category rules / axis pairs**: edit `CATEGORY_RULES` in
  `generate_content.py` — this is the single source of truth for how
  stories get classified and which two poles each category uses.
- **Visual design**: edit `assets/style.css` and the two files under
  `templates/` directly — colors, fonts, spacing, and page structure all
  live there and are never touched by the generation scripts.
- **Logo**: replace `assets/logo-full.png` / `assets/logo-mark.png` with
  new files of the same name to update the brand mark everywhere at once.
- **Site URL / Buttondown username / contact email / governing state**: all
  live in `config.py` — the only file you edit for any of them.

## A note on quality control

This runs unattended, which means nobody is reviewing each day's framing
before it goes live. Worth deciding early on:
- Whether you want a lightweight human spot-check on some cadence (e.g.
  glance at the live page once a week) even though it's not required.
- `content.json` in each Action run, plus the permanent `issues/` archive
  itself, gives you a plain-text history of exactly what was published
  each day, in case a story's framing is ever questioned.
