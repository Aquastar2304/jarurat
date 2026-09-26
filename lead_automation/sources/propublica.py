"""ProPublica Nonprofit Explorer API source (bonus: API integration).

Free, key-less JSON API over IRS tax-exempt organisation filings.
Docs: https://projects.propublica.org/nonprofits/api
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..models import Lead
from .base import LeadSource

log = logging.getLogger(__name__)

SEARCH_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"
PROFILE_URL = "https://projects.propublica.org/nonprofits/organizations/{ein}"

# First letter of the NTEE code -> human readable major group.
NTEE_GROUPS = {
    "A": "Arts, Culture & Humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal-Related",
    "E": "Health Care",
    "F": "Mental Health & Crisis Intervention",
    "G": "Disease / Disorder / Medical Disciplines",
    "H": "Medical Research",
    "I": "Crime & Legal-Related",
    "J": "Employment",
    "K": "Food, Agriculture & Nutrition",
    "L": "Housing & Shelter",
    "M": "Public Safety & Disaster Relief",
    "N": "Recreation & Sports",
    "O": "Youth Development",
    "P": "Human Services",
    "Q": "International Affairs",
    "R": "Civil Rights & Advocacy",
    "S": "Community Improvement",
    "T": "Philanthropy & Grantmaking",
    "U": "Science & Technology",
    "V": "Social Science",
    "W": "Public & Societal Benefit",
    "X": "Religion-Related",
    "Y": "Mutual & Membership Benefit",
    "Z": "Unknown",
}


class ProPublicaSource(LeadSource):
    name = "propublica"

    @staticmethod
    def _category(ntee: str | None) -> str:
        if not ntee:
            return "Nonprofit (US)"
        return f"Nonprofit (US) - {NTEE_GROUPS.get(ntee[0].upper(), 'Other')}"

    @staticmethod
    def _pretty(value: str | None) -> str | None:
        if not value:
            return None
        return value.title() if value.isupper() else value

    def fetch(self, limit: int) -> Iterator[Lead]:
        seen: set[int] = set()
        produced = 0
        for query in self.settings.propublica_queries:
            page = 0
            while produced < limit:
                resp = self.session.get(SEARCH_URL, params={"q": query, "page": page})
                if resp.status_code != 200:
                    log.warning(
                        "ProPublica search '%s' page %d -> HTTP %s", query, page, resp.status_code
                    )
                    break
                orgs = resp.json().get("organizations", [])
                if not orgs:
                    break
                for org in orgs:
                    if produced >= limit:
                        break
                    ein = org.get("ein")
                    if not ein or ein in seen:
                        continue
                    seen.add(ein)
                    city = self._pretty(org.get("city"))
                    state = org.get("state")  # keep the 2-letter state code as-is
                    location = ", ".join(p for p in (city, state) if p)
                    produced += 1
                    yield Lead(
                        name=self._pretty(org.get("name")) or "",
                        source=self.name,
                        source_url=PROFILE_URL.format(ein=ein),
                        category=self._category(org.get("ntee_code")),
                        location=location or None,
                        country="United States",
                        description=(
                            f"IRS-registered nonprofit (EIN {org.get('strein')}); "
                            f"matched search '{query}'."
                        ),
                    )
                page += 1
            log.info("ProPublica query '%s': %d leads so far", query, produced)
