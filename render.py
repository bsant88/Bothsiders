"""
render.py

Takes content.json (produced by generate_content.py) and:
  1. Writes today's issue to issues/YYYY-MM-DD.html (persisted forever).
  2. Writes/overwrites index.html as a copy of today's issue (the homepage
     always shows the latest issue).
  3. Updates manifest.json (the running list of every issue ever published).
  4. Regenerates library.html from the manifest, grouped by month.

The visual design lives entirely in templates/*.html and assets/style.css —
this script only ever fills in placeholders, so the site's look is stable
no matter what content.json contains.
"""

import html
import json
import os
from datetime import datetime

from config import BUTTONDOWN_USERNAME

CONTENT_PATH = "content.json"
MANIFEST_PATH = "manifest.json"
ISSUES_DIR = "issues"
ISSUE_TEMPLATE_PATH = "templates/issue.html"
LIBRARY_TEMPLATE_PATH = "templates/library.html"

CATEGORY_KICKER_FALLBACK = {
    "politics": "POLITICS",
    "economy": "ECONOMY & FISCAL POLICY",
    "business": "BUSINESS",
    "tech": "TECHNOLOGY",
    "sports": "SPORTS",
    "general": "GENERAL",
}

# Badge colors, duplicated from assets/style.css, so the coverage list's
# small category dots match each story's badge without parsing CSS.
CATEGORY_BADGE_COLOR = {
    "politics": "#E4241A",
    "economy": "#9A6B00",
    "business": "#3E4C82",
    "tech": "#6B4C8A",
    "sports": "#1F7A73",
    "general": "#7A5C3E",
}


def esc(text) -> str:
    return html.escape(str(text), quote=False)


def render_bullets(items) -> str:
    return "\n".join(f"          <li>{esc(b)}</li>" for b in items)


def render_evidence_column(items) -> str:
    return "        <ul>\n" + "\n".join(
        f"          <li>{esc(b)}</li>" for b in items
    ) + "\n        </ul>"


def render_story(story: dict, idx: int) -> str:
    category = story.get("category", "general")
    if category not in CATEGORY_KICKER_FALLBACK:
        category = "general"

    return f"""  <article class="story cat-{category}" id="story-{idx}">
    <div class="story-kicker-row">
      <span class="cat-badge">{esc(story.get('category_label', category.upper()))}</span>
      <p class="story-kicker">{esc(story.get('kicker', CATEGORY_KICKER_FALLBACK[category]))}</p>
    </div>
    <h2 class="headline">{idx}. {esc(story['headline'])}</h2>
    <p class="dek">{esc(story['dek'])}</p>

    <div class="duo-banner axis">
      <div class="half a"><span>{esc(story['pole_a_tag'])}</span></div>
      <div class="half b"><span>{esc(story['pole_b_tag'])}</span></div>
      <div class="center-label">{esc(story['center_label'])}</div>
    </div>

    <div class="lenses">
      <div class="lens a">
        <span class="lens-label"><span class="dot"></span>{esc(story['pole_a_label'])}</span>
        <ul>
{render_bullets(story['pole_a_bullets'])}
        </ul>
        <p class="who">{esc(story['pole_a_who'])}</p>
      </div>
      <div class="lens b">
        <span class="lens-label"><span class="dot"></span>{esc(story['pole_b_label'])}</span>
        <ul>
{render_bullets(story['pole_b_bullets'])}
        </ul>
        <p class="who">{esc(story['pole_b_who'])}</p>
      </div>
    </div>

    <div class="duo-banner evd">
      <div class="half a"><span>SOURCED</span></div>
      <div class="half b"><span>VERIFIED</span></div>
      <div class="center-label">WHAT'S DOCUMENTED</div>
    </div>
    <div class="evidence">
      <div class="evidence-grid">
{render_evidence_column(story['evidence_left'])}
{render_evidence_column(story['evidence_right'])}
      </div>
      <p class="sources">{esc(story['sources_line'])}</p>
    </div>
    <p class="back-to-coverage"><a href="#coverage">&uarr; Back to headlines</a></p>
  </article>"""


def render_coverage_card(stories: list) -> str:
    rows = []
    for i, s in enumerate(stories):
        idx = i + 1
        category = s.get("category", "general")
        if category not in CATEGORY_BADGE_COLOR:
            category = "general"
        color = CATEGORY_BADGE_COLOR[category]
        rows.append(
            f'      <li><a href="#story-{idx}">'
            f'<span class="coverage-num">{idx}</span>'
            f'<span class="coverage-dot" style="background:{color}"></span>'
            f'{esc(s["headline"])}</a></li>'
        )
    return (
        '  <div class="coverage-card" id="coverage">\n'
        '    <p class="coverage-label">Today\'s Coverage</p>\n'
        '    <ul class="coverage-list">\n'
        + "\n".join(rows) +
        '\n    </ul>\n  </div>'
    )


def render_issue_page(date_str: str, stories: list, asset_prefix: str, is_today: bool) -> str:
    with open(ISSUE_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    stories_html = "\n\n".join(render_story(s, i + 1) for i, s in enumerate(stories))
    coverage_html = render_coverage_card(stories)
    back_link = "" if is_today else f'<a class="back-link" href="{asset_prefix}library.html">&larr; Back to Library</a>'
    nav_today_class = "active" if is_today else ""
    nav_library_class = "" if is_today else "active"

    return (
        template
        .replace("{{ASSET_PREFIX}}", asset_prefix)
        .replace("{{BUTTONDOWN_USERNAME}}", BUTTONDOWN_USERNAME)
        .replace("{{DATELINE}}", esc(date_str))
        .replace("{{BACK_LINK}}", back_link)
        .replace("{{NAV_TODAY_CLASS}}", nav_today_class)
        .replace("{{NAV_LIBRARY_CLASS}}", nav_library_class)
        .replace("{{COVERAGE}}", coverage_html)
        .replace("{{STORIES}}", stories_html)
    )


def load_manifest() -> list:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_manifest(manifest: list) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def month_label_for(iso_date: str) -> str:
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return dt.strftime("%B %Y")


def day_label_for(iso_date: str) -> str:
    return str(int(iso_date.split("-")[2]))


def render_library(manifest: list) -> str:
    # Group by month, preserving chronological order, newest month first.
    by_month = {}
    order = []
    for entry in sorted(manifest, key=lambda e: e["date"]):
        m = month_label_for(entry["date"])
        if m not in by_month:
            by_month[m] = []
            order.append(m)
        by_month[m].append(entry)

    groups_html = []
    for m in reversed(order):
        entries = by_month[m]
        chips = []
        for e in entries:
            n = e["story_count"]
            label = "story" if n == 1 else "stories"
            chips.append(
                f'      <a class="date-chip" href="issues/{e["date"]}.html">'
                f'{day_label_for(e["date"])}<span>{n} {label}</span></a>'
            )
        groups_html.append(
            f'  <div class="month-group">\n'
            f'    <h3 class="month-label">{esc(m)}</h3>\n'
            f'    <div class="date-chips">\n' + "\n".join(chips) + "\n    </div>\n  </div>"
        )

    with open(LIBRARY_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    return (
        template
        .replace("{{MONTH_GROUPS}}", "\n\n".join(groups_html))
        .replace("{{BUTTONDOWN_USERNAME}}", BUTTONDOWN_USERNAME)
    )


def main():
    with open(CONTENT_PATH, "r", encoding="utf-8") as f:
        content = json.load(f)

    # content.json's date is a display string (e.g. "September 25, 2026");
    # derive the ISO date for filenames from it.
    date_iso = datetime.strptime(content["date"], "%B %d, %Y").strftime("%Y-%m-%d")
    stories = content["stories"]

    os.makedirs(ISSUES_DIR, exist_ok=True)

    # 1. Persisted issue page.
    issue_page = render_issue_page(content["date"], stories, asset_prefix="../", is_today=False)
    with open(os.path.join(ISSUES_DIR, f"{date_iso}.html"), "w", encoding="utf-8") as f:
        f.write(issue_page)

    # 2. Homepage — same content, root-relative asset paths, marked as "today".
    homepage = render_issue_page(content["date"], stories, asset_prefix="", is_today=True)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(homepage)

    # 3. Manifest — add today if not already present, then re-save.
    manifest = load_manifest()
    if not any(e["date"] == date_iso for e in manifest):
        manifest.append({"date": date_iso, "story_count": len(stories)})
    save_manifest(manifest)

    # 4. Library page, rebuilt from the full manifest.
    library_page = render_library(manifest)
    with open("library.html", "w", encoding="utf-8") as f:
        f.write(library_page)

    print(f"Wrote index.html, issues/{date_iso}.html and library.html "
          f"({len(manifest)} issues total)")


if __name__ == "__main__":
    main()
