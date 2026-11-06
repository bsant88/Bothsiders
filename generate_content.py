"""
generate_content.py

Calls the Claude API (with the server-side web_search tool) to research
today's actual top stories and return structured JSON — not raw HTML.
Keeping the model's output to structured data (rather than having it
regenerate the whole page) means the site's design never drifts and the
output is easy to validate before it's published.

Requires:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

Output:
    content.json — a JSON array of story objects, consumed by render.py
"""

import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import anthropic

MODEL = "claude-sonnet-5-5"
TIMEZONE = "America/Los_Angeles"   # change to your preferred timezone

# Story counts: weekdays 5-6 stories, weekends about 3 (by the calendar day in
# TIMEZONE). MIN_* is the floor: below it the run fails and nothing is
# published, so a thin or broken day never replaces the site/emails.
WEEKDAY_TARGET, WEEKDAY_MIN = 6, 4
WEEKEND_TARGET, WEEKEND_MIN = 3, 2

CATEGORY_POLES = {
    "politics": ("POLITICS", "CONSERVATIVE", "LIBERAL", "BOTH SIDES"),
    "economy":  ("ECONOMY", "BULL", "BEAR", "BULL vs BEAR"),
    "business": ("BUSINESS", "GROWTH-FOCUSED", "RISK-FOCUSED", "GROWTH vs RISK"),
    "tech":     ("TECH", "INNOVATION", "OVERSIGHT", "INNOVATION vs OVERSIGHT"),
    "sports":   ("SPORTS", "TAKE", "COUNTER-TAKE", "TAKE vs COUNTER-TAKE"),
    "general":  ("GENERAL", "OPTIMIST", "SKEPTIC", "OPTIMIST vs SKEPTIC"),
}

CATEGORY_RULES = """
Each story must be assigned exactly one category, and each category has a
FIXED pair of poles you must use verbatim — do not invent new pole names:

- politics   -> pole_a_tag "CONSERVATIVE", pole_b_tag "LIBERAL", center_label "BOTH SIDES"
- economy    -> pole_a_tag "BULL", pole_b_tag "BEAR", center_label "BULL vs BEAR"
- business   -> pole_a_tag "GROWTH-FOCUSED", pole_b_tag "RISK-FOCUSED", center_label "GROWTH vs RISK"
- tech       -> pole_a_tag "INNOVATION", pole_b_tag "OVERSIGHT", center_label "INNOVATION vs OVERSIGHT"
- sports     -> pole_a_tag "TAKE", pole_b_tag "COUNTER-TAKE", center_label "TAKE vs COUNTER-TAKE"
- general    -> pole_a_tag "OPTIMIST", pole_b_tag "SKEPTIC", center_label "OPTIMIST vs SKEPTIC"

Use "politics" whenever the real disagreement is fundamentally right vs.
left, regardless of the story's surface subject matter (e.g. a Fed policy
fight framed around partisan blame is "politics", not "economy"; a market
story about how investors are reading the same data is "economy").
"""

SYSTEM_PROMPT = f"""You are producing content for Bothsiders, a daily news
page that presents each top story from two argued perspectives plus a
neutral, sourced facts section underneath.

{CATEGORY_RULES}

For EACH story, write:
- A short, accurate headline and one-sentence dek (deck/subhead).
- Four bullets for each pole representing the STRONGEST, most honest
  version of that side's actual argument — steelman it, never strawman it.
  These are positions real people/commentators hold, not your own opinions.
- A one-line "who" attribution for each side (e.g. "Positions commonly
  voiced by X").
- A neutral evidence section: 4 bullets total (2+2) of plainly documented,
  sourced facts — things that are on the record, not spin from either side.
- A one-line sources attribution naming real outlets/reports you found via
  search.

Ground every story in ACTUAL news from your web searches — do not invent
events. Prefer stories from the last 24-48 hours. Try to cover a spread of
categories rather than all stories in one bucket, but only if enough
real news supports it — never force a category onto a story that doesn't
fit it.

EDITORIAL RULES (follow every one):
- Corroboration: include a story only if its core facts are confirmed by at
  least two independent outlets, or by a primary source (court filing,
  agency or company release, official transcript). Skip a story that rests
  on a single unconfirmed report. Never pad the count with weak items.
- Flag weaker sourcing inside the story text. If one specific claim comes
  from a single outlet or is unconfirmed, say so in the evidence bullets
  (for example "reported by X; not independently confirmed").
- When sources disagree on a number or fact, state both figures and name who
  reported each. Do not pick one silently.
- Neutral voice: no first-person wording (no "I", "we", "our", "my") anywhere
  in the story text. Do not tell readers what to think. The two sides'
  arguments are attributed to the people or groups who make them.
- The evidence bullets contain only documented facts, with figures, dates and
  names — no adjectives that favor either side.
- Do not state a fact you did not see in your search results. If you could not
  confirm something, leave it out.
- "sources": 2-4 outlets or primary documents actually used for that story.
  Each "url" must be the exact URL of a page that appeared in your search
  results. Never write a URL from memory.

Output ONLY a JSON array (no prose, no markdown fences, no commentary)
matching this exact schema per story:

{{
  "category": "politics|economy|business|tech|sports|general",
  "category_label": "POLITICS",
  "kicker": "SHORT SECTION LABEL",
  "headline": "...",
  "dek": "...",
  "pole_a_tag": "CONSERVATIVE",
  "pole_b_tag": "LIBERAL",
  "center_label": "BOTH SIDES",
  "pole_a_label": "Conservative view",
  "pole_b_label": "Liberal view",
  "pole_a_bullets": ["...", "...", "...", "..."],
  "pole_b_bullets": ["...", "...", "...", "..."],
  "pole_a_who": "...",
  "pole_b_who": "...",
  "evidence_left": ["...", "..."],
  "evidence_right": ["...", "..."],
  "sources": [{{"name": "Outlet name", "url": "https://exact-url-from-search-results"}}]
}}
"""


def today_string() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%B %d, %Y")


def story_counts():
    """(target, minimum) number of stories for today's calendar day."""
    weekday = datetime.now(ZoneInfo(TIMEZONE)).weekday()   # Mon=0 ... Sun=6
    if weekday >= 5:
        return WEEKEND_TARGET, WEEKEND_MIN
    return WEEKDAY_TARGET, WEEKDAY_MIN


def extract_json_array(text: str):
    """Pull a JSON array out of the model's response, tolerating stray
    markdown fences or leading/trailing prose if the model adds any."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in model output")
    return json.loads(match.group(0))


# ---------- source-link verification ----------

def _url_key(url: str):
    """Compare URLs by host + path, ignoring scheme, www, query and fragment."""
    parts = urlparse(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host, parts.path.rstrip("/")


def collect_urls(response, seen: dict):
    """Record every URL the web search actually returned or cited."""
    for block in response.content:
        if block.type == "web_search_tool_result" and isinstance(block.content, list):
            for r in block.content:
                url = getattr(r, "url", None)
                if url:
                    seen.setdefault(_url_key(url), url)
        if block.type == "text":
            for c in getattr(block, "citations", None) or []:
                url = getattr(c, "url", None)
                if url:
                    seen.setdefault(_url_key(url), url)


def is_primary_domain(host: str) -> bool:
    return host.endswith((".gov", ".mil")) or host in ("supremecourt.gov",)


def verified_sources(story: dict, seen: dict):
    """Keep only sources whose URL was really returned by the search."""
    good, hosts = [], set()
    for src in story.get("sources") or []:
        if not isinstance(src, dict):
            continue
        name = str(src.get("name", "")).strip()
        url = str(src.get("url", "")).strip()
        key = _url_key(url) if url else None
        if not name or key not in seen:
            continue
        if key[0] in hosts:
            continue
        hosts.add(key[0])
        good.append({"name": name, "url": seen[key]})
    return good


# ---------- story validation ----------

TEXT_FIELDS = ["headline", "dek", "pole_a_who", "pole_b_who"]
LIST_FIELDS = {"pole_a_bullets": 4, "pole_b_bullets": 4,
               "evidence_left": 2, "evidence_right": 2}
FIRST_PERSON = re.compile(r"\b(I|I'm|I've|we|We|our|Our|my|My)\b")


def clean_story(raw, seen: dict, date_str: str):
    """Return a validated, normalized story dict, or (None, reason)."""
    if not isinstance(raw, dict):
        return None, "not an object"
    s = dict(raw)

    category = s.get("category")
    if category not in CATEGORY_POLES:
        return None, f"unknown category {category!r}"
    label, tag_a, tag_b, center = CATEGORY_POLES[category]
    # Poles are fixed by category, so never trust the model's wording here.
    s.update(category_label=label, pole_a_tag=tag_a, pole_b_tag=tag_b,
             center_label=center)
    s.setdefault("kicker", label)
    s["pole_a_label"] = str(s.get("pole_a_label") or f"{tag_a.title()} view")
    s["pole_b_label"] = str(s.get("pole_b_label") or f"{tag_b.title()} view")

    for field in TEXT_FIELDS:
        if not str(s.get(field, "")).strip():
            return None, f"missing {field}"
    for field, n in LIST_FIELDS.items():
        items = s.get(field)
        if (not isinstance(items, list) or len(items) != n
                or not all(isinstance(i, str) and i.strip() for i in items)):
            return None, f"{field} must be {n} non-empty strings"

    sources = verified_sources(s, seen)
    if not sources:
        return None, "no source link matched the search results"
    s["sources"] = sources
    s["sources_date"] = date_str
    s["sources_line"] = (
        "Sourced from " + ", ".join(x["name"] for x in sources) + f", {date_str}."
    )

    text = " ".join(
        [str(s[f]) for f in TEXT_FIELDS]
        + [i for f in LIST_FIELDS for i in s[f]]
    )
    if FIRST_PERSON.search(text):
        print(f"WARNING: first-person wording in: {s['headline']}")
    if len(sources) < 2 and not is_primary_domain(sources[0]["url"].split("/")[2]):
        print(f"WARNING: only one verified source link for: {s['headline']}")
    return s, None


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set")

    if os.path.exists("content.json"):
        os.remove("content.json")   # never reuse a previous day's file

    client = anthropic.Anthropic(api_key=api_key)
    date_str = today_string()
    target, minimum = story_counts()
    day_name = datetime.now(ZoneInfo(TIMEZONE)).strftime("%A")
    count_rule = (
        f"Produce exactly {target} stories." if target <= 3 else
        f"Produce {target} stories. If fewer than {target} are well "
        f"corroborated, produce {target - 1}; never fewer than {minimum} and "
        f"never pad with weak items."
    )

    user_prompt = (
        f"Today is {day_name}, {date_str}. Research today's actual top news "
        f"stories using web search, then produce the stories as a JSON array "
        f"following the schema and editorial rules in your system prompt. "
        f"{count_rule} Search thoroughly (at least 8-10 searches across "
        f"different topics/categories) and confirm each story's key facts "
        f"with a second outlet or primary source before writing it. Keep the "
        f"answer compact: every bullet and sentence short, no more text "
        f"than the schema needs. Your final message must contain only the "
        f"JSON array."
    )

    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 20}]
    messages = [{"role": "user", "content": user_prompt}]
    MAX_TOKENS = 32000
    seen_urls = {}

    def text_of(resp):
        return "".join(b.text for b in resp.content if b.type == "text")

    def ask(**kwargs):
        # Streaming is required by the API for requests with large token
        # limits; this collects the finished message the same way.
        with client.messages.stream(model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT, **kwargs) as stream:
            return stream.get_final_message()

    # The web search tool can pause a long turn; keep going until it finishes.
    response = None
    for _ in range(6):
        response = ask(tools=tools, messages=messages)
        collect_urls(response, seen_urls)
        if response.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": response.content})

    full_text = text_of(response)
    print(f"stop_reason={response.stop_reason}, text length={len(full_text)}, "
          f"search URLs seen={len(seen_urls)}")

    try:
        if response.stop_reason == "max_tokens":
            raise ValueError("Answer was cut off")
        raw_stories = extract_json_array(full_text)
    except (ValueError, json.JSONDecodeError):
        # Start a fresh request (no tools, no earlier reasoning blocks) and
        # hand over the earlier text as plain text to turn into a clean array.
        print("First answer was unusable. Asking for a clean JSON array.")
        print("Start of that answer:", full_text[:300])
        retry = ask(
            messages=[{
                "role": "user",
                "content": (
                    f"Today is {day_name}, {date_str}. Below is a draft of "
                    f"today's Bothsiders stories, possibly cut off or mixed "
                    f"with other text. Output the complete, valid JSON array "
                    f"following the schema in your system prompt, keeping "
                    f"every bullet short and keeping each source URL exactly "
                    f"as written in the draft. If the draft has fewer "
                    f"complete stories, return only the complete ones. "
                    f"Output only the JSON array, with no other text."
                    f"\n\nDRAFT:\n{full_text}"
                ),
            }],
        )
        retry_text = text_of(retry)
        print(f"retry stop_reason={retry.stop_reason}, text length={len(retry_text)}")
        try:
            raw_stories = extract_json_array(retry_text)
        except (ValueError, json.JSONDecodeError):
            print("Start of retry answer:", retry_text[:500])
            sys.exit("FAILED: could not get a valid JSON story list from the model. Nothing was published.")

    if not isinstance(raw_stories, list):
        sys.exit("FAILED: model did not return a story list. Nothing was published.")

    stories, seen_headlines = [], set()
    for raw in raw_stories:
        story, reason = clean_story(raw, seen_urls, date_str)
        title = raw.get("headline", "?") if isinstance(raw, dict) else "?"
        if story is None:
            print(f"Dropped story ({reason}): {title}")
            continue
        key = story["headline"].strip().lower()
        if key in seen_headlines:
            print(f"Dropped duplicate: {title}")
            continue
        seen_headlines.add(key)
        stories.append(story)

    stories = stories[:target]
    if len(stories) < minimum:
        sys.exit(
            f"FAILED: only {len(stories)} valid stories (need at least {minimum} "
            f"on a {day_name}). Nothing was published and no email was sent."
        )
    if len(stories) < target:
        print(f"Note: {len(stories)} stories today (target {target}).")

    with open("content.json", "w", encoding="utf-8") as f:
        json.dump(
            {"date": date_str, "stories": stories},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Wrote content.json with {len(stories)} stories for {date_str}")


if __name__ == "__main__":
    main()
