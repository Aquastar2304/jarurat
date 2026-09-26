"""Wikipedia source.

1. Uses the MediaWiki API to list the pages inside configured categories
   (e.g. "Health charities in India").
2. Scrapes each page's infobox with BeautifulSoup to pull the official
   website and headquarters/location, plus the first paragraph as a short
   description.
"""

from __future__ import annotations

import logging
import re
from typing import Iterator
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

from ..models import Lead
from .base import LeadSource

log = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
PAGE_URL = "https://en.wikipedia.org/wiki/{title}"

# Infobox rows that describe where an organisation is, in priority order.
LOCATION_KEYS = ("headquarters", "location", "founded at", "region served", "area served")
SKIP_TITLE_PREFIXES = ("List of", "Lists of", "Category:", "Template:", "Portal:")
_CITATION = re.compile(r"\[\s*(?:\d+|[a-z]|note \d+|citation needed)\s*\]", re.I)
_JUNK_SELECTOR = (
    "sup, .reference, .noprint, .mw-kartographer-maplink, "
    "#coordinates, .geo, .geo-dms, .geo-dec, .geo-multi-punct, .geo-inline, .geo-inline-hidden, "
    "[style*='display:none'], [style*='display: none']"
)
_COORDS = re.compile(r"\s*\d{1,3}°.*$")  # anything from a degree sign onwards is a map coordinate
_WORD = re.compile(r"[a-z0-9]+")
_GENERIC_WORDS = {"india", "indian", "trust", "foundation", "society", "association", "organisation", "organization", "centre", "center", "institute", "hospital"}
_NON_WEBSITE_HOSTS = (
    "wikipedia.org", "wikimedia.org", "wikidata.org", "archive.org",
    "wikisource.org", "worldcat.org", "doi.org", "google.com",
)


def _tidy(text: str) -> str:
    """Normalise spacing artefacts left by get_text(" ") and drop citations."""
    text = _CITATION.sub("", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,;")


class WikipediaSource(LeadSource):
    name = "wikipedia"

    # ---- category listing -------------------------------------------------
    def _category_members(self, category: str) -> list[str]:
        titles: list[str] = []
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmnamespace": 0,  # articles only
            "cmlimit": 100,
            "format": "json",
        }
        while True:
            resp = self.session.get(API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            titles.extend(m["title"] for m in data["query"]["categorymembers"])
            cont = data.get("continue")
            if not cont:
                break
            params.update(cont)
        return [t for t in titles if not t.startswith(SKIP_TITLE_PREFIXES)]

    # ---- page scraping ----------------------------------------------------
    @staticmethod
    def _cell_text(cell: Tag) -> str:
        # Remove citations, hidden map helpers ("See TfM") and other noise.
        for junk in cell.select(_JUNK_SELECTOR):
            junk.decompose()
        return _tidy(_COORDS.sub("", cell.get_text(" ", strip=True)))

    def _parse_infobox(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        box = soup.select_one("table.infobox")
        if box is None:
            return None, None
        website: str | None = None
        rows: dict[str, str] = {}
        for tr in box.select("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not (th and td):
                continue
            key = th.get_text(" ", strip=True).lower()
            if "website" in key and website is None:
                link = td.find("a", href=True)
                if link:
                    website = link["href"]
                continue
            rows[key] = self._cell_text(td)
        location = next((rows[k] for k in LOCATION_KEYS if rows.get(k)), None)
        return website, location

    @staticmethod
    def _first_paragraph(soup: BeautifulSoup) -> str | None:
        content = soup.select_one("#mw-content-text .mw-parser-output")
        if content is None:
            return None
        for p in content.find_all("p"):
            if "mw-empty-elt" in p.get("class", []):
                continue
            text = _tidy(p.get_text(" ", strip=True))
            if len(text) > 40:
                if len(text) <= 220:
                    return text
                return text[:220].rsplit(" ", 1)[0] + "..."
        return None

    @staticmethod
    def _external_links_website(soup: BeautifulSoup, title: str) -> str | None:
        """Official site from the 'External links' section, used when the infobox has none.

        Only a link whose list item says "official" or mentions a distinctive word of
        the page title is accepted, so links to related organisations are not mistaken
        for the lead's own website.
        """
        heading = soup.select_one("#External_links")
        if heading is None:
            return None
        title_words = {w for w in _WORD.findall(title.lower()) if len(w) > 3 and w not in _GENERIC_WORDS}
        node = heading.find_parent(["h2", "h3", "div"]) or heading
        for sibling in node.find_next_siblings():
            if sibling.name in ("h2", "h3") or sibling.select_one("h2, h3"):
                break
            for li in sibling.select("li"):
                a = li.select_one("a.external[href]")
                if a is None:
                    continue
                href = a["href"]
                if not href.startswith("http") or any(h in href for h in _NON_WEBSITE_HOSTS):
                    continue
                text = li.get_text(" ", strip=True).lower()
                if "official" in text or title_words & set(_WORD.findall(text)):
                    return href
        return None

    def _scrape_page(self, title: str, category: str) -> Lead | None:
        url = PAGE_URL.format(title=quote(title.replace(" ", "_")))
        resp = self.session.get(url)
        if resp.status_code != 200:
            log.warning("Skipping %s (HTTP %s)", title, resp.status_code)
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        website, location = self._parse_infobox(soup)
        website = website or self._external_links_website(soup, title)
        return Lead(
            name=title,
            source=self.name,
            source_url=url,
            category=category.removeprefix("Category:"),
            website=website,
            location=location,
            country="India" if "India" in category else None,
            description=self._first_paragraph(soup),
        )

    # ---- public API -------------------------------------------------------
    def fetch(self, limit: int) -> Iterator[Lead]:
        seen: set[str] = set()
        produced = 0
        for category in self.settings.wiki_categories:
            try:
                titles = self._category_members(category)
            except Exception as exc:  # noqa: BLE001 - keep going with other categories
                log.error("Could not list %s: %s", category, exc)
                continue
            log.info("%s: %d candidate pages", category, len(titles))
            for title in titles:
                if produced >= limit:
                    return
                if title in seen:
                    continue
                seen.add(title)
                try:
                    lead = self._scrape_page(title, category)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Failed to scrape %s: %s", title, exc)
                    continue
                if lead:
                    produced += 1
                    yield lead
