"""
send_email.py

Takes content.json (the same file render.py consumes) and sends today's
issue to every Buttondown subscriber automatically, branded to match the
site: logo, brand colors, and the same category badges.

Why this is hand-built HTML with inline styles, not the site's actual
CSS: email clients (Outlook especially) don't support flexbox, grid, CSS
variables, or <style> blocks reliably. Every style here is applied inline,
directly on each element, which is the one approach that survives across
Gmail, Apple Mail, Outlook, and the rest. It's more verbose than the
website's CSS, but it's what actually renders consistently in an inbox.

The logo is a hosted <img> pointing at the live site's own asset file
(SITE_BASE_URL + /assets/...) rather than an embedded/base64 image —
inline images are stripped or blocked by most mail clients, but a normal
hosted image loads like any other web image.

Requires:
    pip install requests
    export BUTTONDOWN_API_KEY=...

Run this AFTER render.py in the same job, so content.json still reflects
today's issue and the linked issue page — and the logo files — already
exist on the live site.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from config import SITE_BASE_URL
from sources import sources_html, strip_citations

CONTENT_PATH = "content.json"
BUTTONDOWN_API_URL = "https://api.buttondown.email/v1/emails"

# The email is handed to Buttondown ahead of time and scheduled for this
# local time, so it lands at the same moment even if GitHub starts the job
# late. If that time has already passed, it is sent right away instead.
SEND_TIMEZONE = "America/Los_Angeles"
SEND_HOUR = 5   # 5:00 AM Pacific = 8:00 AM Eastern

# Same palette as assets/style.css — badge color, then the two poles.
CATEGORY_COLORS = {
    "politics": {"badge": "#E4241A", "a": "#E4241A", "b": "#0A84C7"},
    "economy":  {"badge": "#9A6B00", "a": "#2E6B3E", "b": "#8C2F2F"},
    "business": {"badge": "#3E4C82", "a": "#4A6FA5", "b": "#B06A2E"},
    "tech":     {"badge": "#6B4C8A", "a": "#1E7A8C", "b": "#4A4A52"},
    "sports":   {"badge": "#1F7A73", "a": "#B8860B", "b": "#2F5D8A"},
    "general":  {"badge": "#7A5C3E", "a": "#4C8C5C", "b": "#6B6B63"},
}
BRAND_NAVY = "#12204B"
INK = "#16181D"
INK_SOFT = "#63666E"
LINE = "#E7E7EA"
EVD = "#3F7A4C"
EVD_TINT = "#EFF6F0"
EVD_TINT_LINE = "#CFE6D3"


def bullets_html(items) -> str:
    lis = "".join(
        f'<li style="margin-bottom:8px;">{b}</li>' for b in items
    )
    return f'<ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.6;color:{INK};">{lis}</ul>'


def viewpoint_block(color: str, label: str, bullets: list, who: str) -> str:
    return f"""
<div style="border-left:4px solid {color};background:#F7F7F8;border-radius:0 8px 8px 0;padding:16px 20px;margin-bottom:12px;">
  <p style="margin:0 0 10px;font-weight:700;font-size:13px;color:{color};">{label}</p>
  {bullets_html(bullets)}
  <p style="margin:12px 0 0;font-size:12px;color:{INK_SOFT};font-style:italic;">{who}</p>
</div>"""


def story_html(story: dict, idx: int) -> str:
    colors = CATEGORY_COLORS.get(story.get("category", "general"), CATEGORY_COLORS["general"])
    category_label = story.get("category_label", story.get("category", "").upper())

    evidence_items = story["evidence_left"] + story["evidence_right"]
    evidence_lis = "".join(
        f'<li style="margin-bottom:8px;">{b}</li>' for b in evidence_items
    )

    return f"""
<div id="story-{idx}" style="margin-bottom:14px;">
  <span style="display:inline-block;background:{colors['badge']};color:#ffffff;font-size:11px;font-weight:700;letter-spacing:0.05em;padding:4px 10px;border-radius:4px;">{category_label}</span>
</div>
<h2 style="font-size:20px;font-weight:800;line-height:1.3;margin:0 0 10px;color:{INK};">{idx}. {story['headline']}</h2>
<p style="font-size:14.5px;line-height:1.6;color:{INK_SOFT};margin:0 0 20px;">{story['dek']}</p>

{viewpoint_block(colors['a'], story['pole_a_label'], story['pole_a_bullets'], story['pole_a_who'])}
{viewpoint_block(colors['b'], story['pole_b_label'], story['pole_b_bullets'], story['pole_b_who'])}

<div style="background:{EVD_TINT};border:1px solid {EVD_TINT_LINE};border-radius:8px;padding:16px 20px;margin-top:4px;">
  <p style="margin:0 0 10px;font-weight:700;font-size:12px;color:{EVD};text-transform:uppercase;letter-spacing:0.04em;">What's documented</p>
  <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.6;color:{INK};">{evidence_lis}</ul>
  <p style="margin:12px 0 0;font-size:12px;color:{INK_SOFT};">{sources_html(story, "color:#63666E;text-decoration:underline;")}</p>
</div>

<p style="text-align:center;margin:16px 0 0;">
  <a href="#coverage" style="font-size:12.5px;font-weight:600;color:{INK_SOFT};text-decoration:none;">&uarr; Back to headlines</a>
</p>

<hr style="border:none;border-top:1px solid {LINE};margin:36px 0;">
"""


def coverage_html(stories: list) -> str:
    rows = []
    for i, s in enumerate(stories):
        idx = i + 1
        colors = CATEGORY_COLORS.get(s.get("category", "general"), CATEGORY_COLORS["general"])
        border_top = f"border-top:1px solid {LINE};" if i > 0 else ""
        rows.append(f"""
<tr>
  <td style="padding:0;">
    <a href="#story-{idx}" style="display:block;{border_top}padding:10px 16px;text-decoration:none;color:{INK};font-size:13.5px;font-weight:600;">
      <span style="display:inline-block;width:16px;font-size:11px;color:{INK_SOFT};font-weight:700;">{idx}</span>
      <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{colors['badge']};margin:0 8px 1px 2px;"></span>{s['headline']}
    </a>
  </td>
</tr>""")
    rows_html = "".join(rows)
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" id="coverage" style="border:1px solid {LINE};border-radius:12px;background:#F7F7F8;margin:0 0 28px;">
  <tr><td style="padding:14px 16px 6px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:{INK_SOFT};">Today's Coverage</td></tr>
  {rows_html}
</table>
"""


def build_email_html(content: dict) -> str:
    date_iso = datetime.strptime(content["date"], "%B %d, %Y").strftime("%Y-%m-%d")
    issue_url = f"{SITE_BASE_URL}/issues/{date_iso}.html"
    library_url = f"{SITE_BASE_URL}/past-issues.html"
    logo_url = f"{SITE_BASE_URL}/assets/logo-full.png"
    mark_url = f"{SITE_BASE_URL}/assets/logo-mark.png"

    stories_html = "\n".join(
        story_html(s, i + 1) for i, s in enumerate(content["stories"])
    )

    return f"""
<div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">

  <div style="text-align:center;padding:20px 0 10px;">
    <img src="{logo_url}" width="300" alt="Bothsiders" style="display:block;margin:0 auto;width:300px;max-width:80%;height:auto;border:0;">
  </div>
  <div style="background:#F7F7F8;border:1px solid #E7E7EA;border-radius:14px;padding:28px 14px;margin:26px 0 30px;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
      <td width="33%" valign="top" style="padding:0 12px;text-align:center;">
        <div style="border-top:4px solid #E4241A;padding-top:12px;font-size:12px;font-weight:800;letter-spacing:0.1em;color:#E4241A;">EXPLORE</div>
        <div style="font-size:13.5px;line-height:1.55;color:#63666E;padding-top:9px;">Both sides of today&rsquo;s top stories, plus the plain, simple facts.</div>
      </td><td width="33%" valign="top" style="padding:0 12px;text-align:center;">
        <div style="border-top:4px solid #3F7A4C;padding-top:12px;font-size:12px;font-weight:800;letter-spacing:0.1em;color:#3F7A4C;">COMPARE</div>
        <div style="font-size:13.5px;line-height:1.55;color:#63666E;padding-top:9px;">No spin. No lecture. Sourced.</div>
      </td><td width="33%" valign="top" style="padding:0 12px;text-align:center;">
        <div style="border-top:4px solid #0A84C7;padding-top:12px;font-size:12px;font-weight:800;letter-spacing:0.1em;color:#0A84C7;">DECIDE</div>
        <div style="font-size:13.5px;line-height:1.55;color:#63666E;padding-top:9px;">How do <strong style="color:#16181D;">YOU</strong> see it?</div>
      </td>
    </tr></table>
  </div>
  <p style="text-align:center;font-size:13px;font-weight:700;letter-spacing:0.02em;color:{INK_SOFT};margin:14px 0 4px;">For the day of {content['date']}</p>
  <p style="text-align:center;margin:0 0 22px;">
    <a href="{issue_url}" style="font-size:13px;font-weight:600;color:#0A84C7;text-decoration:none;">Read this issue on the web &rarr;</a>
  </p>

  {coverage_html(content['stories'])}

  <div style="border-top:4px solid {BRAND_NAVY};margin-bottom:32px;"></div>

  {stories_html}

  <div style="text-align:center;padding:12px 0 6px;">
    <img src="{mark_url}" width="30" alt="" style="display:block;margin:0 auto 12px;border:0;">
    <p style="font-size:12px;color:#999999;margin:0 0 6px;">Bothsiders &mdash; Explore. Compare. Decide.</p>
    <p style="font-size:12px;margin:0;">
      <a href="{library_url}" style="color:#0A84C7;text-decoration:none;">Browse past issues</a>
    </p>
  </div>

</div>
"""


def main():
    api_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not api_key:
        sys.exit("BUTTONDOWN_API_KEY is not set")

    with open(CONTENT_PATH, "r", encoding="utf-8") as f:
        content = strip_citations(json.load(f))

    # Once-per-day guard: a marker file records that this date's issue was
    # emailed, so re-running the job can never email subscribers twice.
    date_iso = datetime.strptime(content["date"], "%B %d, %Y").strftime("%Y-%m-%d")
    marker = os.path.join("sent", f"{date_iso}.txt")
    if os.path.exists(marker):
        print(f"Already emailed the {date_iso} issue. Skipping.")
        return

    subject = f"Bothsiders — {content['date']}"
    body = build_email_html(content)

    send_at = datetime.strptime(date_iso, "%Y-%m-%d").replace(
        hour=SEND_HOUR, tzinfo=ZoneInfo(SEND_TIMEZONE)
    )
    payload = {"subject": subject, "body": body}
    if send_at > datetime.now(timezone.utc) + timedelta(minutes=3):
        payload["status"] = "scheduled"
        payload["publish_date"] = send_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"Scheduling for {send_at.isoformat()}")
    else:
        payload["status"] = "about_to_send"   # sends immediately
        print("Send time already passed; sending now.")

    response = requests.post(
        BUTTONDOWN_API_URL,
        headers={
            "Authorization": f"Token {api_key}",
            # Buttondown's safety check: required to send for real (not as a
            # draft). Needed for real sends and scheduled sends.
            "X-Buttondown-Live-Dangerously": "true",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code >= 300:
        sys.exit(f"Buttondown API error {response.status_code}: {response.text}")

    os.makedirs("sent", exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"{response.json().get('id')}\n")
    print(f"Sent '{subject}' — Buttondown email id: {response.json().get('id')}")


if __name__ == "__main__":
    main()
