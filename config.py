"""
config.py

Single place to set the few values every script needs. Edit these once
after you've registered a domain and created your Buttondown account —
nothing else in the codebase needs to change.
"""

# Your live site's base URL, no trailing slash. Used to build links in the
# email newsletter back to the full web page. Update this once you know
# your GitHub Pages URL or custom domain.
SITE_BASE_URL = "https://yourusername.github.io/bothsiders"

# Your Buttondown username (the part after buttondown.email/ in your
# newsletter's URL). Used for the signup form embedded on every page.
BUTTONDOWN_USERNAME = "yourusername"

# The email address shown on the Privacy Policy and Terms & Conditions
# pages for legal/privacy inquiries. Use a real inbox you check.
CONTACT_EMAIL = "hello@yourdomain.com"

# The state whose law governs the Terms & Conditions. Plain text, used
# as-is in the "Governing Law" section.
GOVERNING_LAW_STATE = "California"
