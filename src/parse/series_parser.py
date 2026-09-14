"""Extract LOCG series ids from issue-page HTML."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# /comics/series/210130/clayface-celebrity-dirt
_SERIES_HREF_RE = re.compile(
    r"/comics/series/(?P<series_id>\d+)(?:/|\?|#|$)",
    re.IGNORECASE,
)


def parse_series_id_from_issue_html(html_content: str) -> int | None:
    """Return LOCG series id from an issue detail page, or None if absent."""
    soup = BeautifulSoup(html_content, "html.parser")

    for anchor in soup.find_all("a", href=True):
        match = _SERIES_HREF_RE.search(anchor["href"])
        if match:
            return int(match.group("series_id"))

    # Fallback: raw HTML (JSON blobs, meta tags, etc.)
    match = _SERIES_HREF_RE.search(html_content)
    if match:
        return int(match.group("series_id"))

    return None


def build_issue_page_url(locg_issue_id: int, issue_path: str | None = None) -> str:
    """Build absolute LOCG issue URL from path or locg id."""
    if issue_path:
        if issue_path.startswith("http"):
            return issue_path
        return f"https://leagueofcomicgeeks.com{issue_path}"
    return f"https://leagueofcomicgeeks.com/comic/{int(locg_issue_id)}"
