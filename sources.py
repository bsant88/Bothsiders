"""
sources.py

Turns a story's list of verified sources into the "Sourced from ..." line,
with each outlet name linked to the actual article. Shared by render.py (the
website) and send_email.py (the email) so both show the same links.

Falls back to the plain-text `sources_line` if a story has no source links.
"""

import html
import re


def _join(links):
    if len(links) <= 1:
        return "".join(links)
    return ", ".join(links[:-1]) + " and " + links[-1]


def sources_html(story: dict, link_style: str = "") -> str:
    style = f' style="{link_style}"' if link_style else ""
    links = []
    for s in story.get("sources") or []:
        name = str(s.get("name", "")).strip()
        url = str(s.get("url", "")).strip()
        if not name or not url.startswith(("http://", "https://")):
            continue
        links.append(
            f'<a href="{html.escape(url, quote=True)}" target="_blank" '
            f'rel="noopener"{style}>{html.escape(name, quote=False)}</a>'
        )
    if not links:
        return html.escape(str(story.get("sources_line", "")), quote=False)
    date = str(story.get("sources_date", "")).strip()
    tail = f", {html.escape(date, quote=False)}." if date else "."
    return "Sourced from " + _join(links) + tail


_CITE_TAG = re.compile(r"</?cite\b[^>]*>", re.IGNORECASE)


def strip_citations(obj):
    """Remove the <cite ...> / </cite> markup that web search can leave inside
    the model's text, in any string nested in lists or dicts. The words inside
    the tags are kept."""
    if isinstance(obj, str):
        return _CITE_TAG.sub("", obj).replace("  ", " ").strip()
    if isinstance(obj, list):
        return [strip_citations(x) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k == "sources" else strip_citations(v)) for k, v in obj.items()}
    return obj
