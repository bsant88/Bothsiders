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
from zoneinfo import ZoneInfo

import anthropic

MODEL = "claude-sonnet-5-5"
TIMEZONE = "America/Los_Angeles"   # change to your preferred timezone
NUM_STORIES = 6

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
categories rather than 6 stories all in one bucket, but only if enough
real news supports it — never force a category onto a story that doesn't
fit it.

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
  "sources_line": "Sourced from X, Y and Z, Month Day, Year."
}}
"""


def today_string() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%B %d, %Y")


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


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    date_str = today_string()

    user_prompt = (
        f"Today's date is {date_str}. Research today's actual top news "
        f"stories using web search, then produce exactly {NUM_STORIES} "
        f"stories as a JSON array following the schema and rules in your "
        f"system prompt. Search thoroughly (at least 8-10 searches across "
        f"different topics/categories) before writing anything."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 20}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Concatenate all text blocks in the final response (tool calls/results
    # are handled server-side for web_search, so this is the model's
    # finished answer after searching).
    full_text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    stories = extract_json_array(full_text)

    if not isinstance(stories, list) or len(stories) == 0:
        sys.exit("Model did not return a valid story list")

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
