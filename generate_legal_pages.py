"""
generate_legal_pages.py

Renders privacy-policy.html and terms.html from templates/privacy.html and
templates/terms.html, filling in the values from config.py.

This is NOT part of the daily automation — legal pages don't change based
on the day's news. Run this once after you've filled in config.py, and
again any time you actually edit the policy text or your contact details.

Usage:
    python generate_legal_pages.py
"""

from datetime import date

from config import SITE_BASE_URL, CONTACT_EMAIL, GOVERNING_LAW_STATE

PAGES = [
    ("templates/privacy.html", "privacy-policy.html"),
    ("templates/terms.html", "terms.html"),
]


def main():
    last_updated = date.today().strftime("%B %d, %Y")

    for template_path, output_path in PAGES:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = (
            content
            .replace("{{SITE_BASE_URL}}", SITE_BASE_URL)
            .replace("{{CONTACT_EMAIL}}", CONTACT_EMAIL)
            .replace("{{GOVERNING_LAW_STATE}}", GOVERNING_LAW_STATE)
            .replace("{{LAST_UPDATED}}", last_updated)
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
