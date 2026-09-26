"""Wikidata SPARQL source (bonus: API integration).

One structured query against https://query.wikidata.org returns every
nonprofit / NGO / charity / foundation registered for a country together
with its official website (P856), published email (P968), headquarters
(P159) and a one-line description. No scraping, no API key.
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..models import Lead
from .base import LeadSource

log = logging.getLogger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"
ENTITY_URL = "https://www.wikidata.org/wiki/{qid}"

# Organisation types: NGO, nonprofit organization, charitable organization, foundation.
ORG_TYPES = ("wd:Q79913", "wd:Q163740", "wd:Q708676", "wd:Q157031")
COUNTRY_LABELS = {"Q668": "India", "Q30": "United States", "Q145": "United Kingdom"}

QUERY = """
SELECT ?org ?orgLabel (SAMPLE(?website) AS ?site) (SAMPLE(?email) AS ?mail)
       (SAMPLE(?hqLabel) AS ?hq) (SAMPLE(?typeLabel) AS ?kind) (SAMPLE(?desc) AS ?description)
WHERE {{
  VALUES ?type {{ {types} }}
  ?org wdt:P31 ?type ; wdt:P17 wd:{country} ; wdt:P856 ?website .
  ?org rdfs:label ?orgLabel FILTER(LANG(?orgLabel) = "en")
  ?type rdfs:label ?typeLabel FILTER(LANG(?typeLabel) = "en")
  OPTIONAL {{ ?org wdt:P968 ?email . }}
  OPTIONAL {{ ?org wdt:P159 ?hq . ?hq rdfs:label ?hqLabel FILTER(LANG(?hqLabel) = "en") }}
  OPTIONAL {{ ?org schema:description ?desc FILTER(LANG(?desc) = "en") }}
}}
GROUP BY ?org ?orgLabel
ORDER BY ?orgLabel
LIMIT {limit}
"""


class WikidataSource(LeadSource):
    name = "wikidata"

    def fetch(self, limit: int) -> Iterator[Lead]:
        country = self.settings.wikidata_country
        query = QUERY.format(types=" ".join(ORG_TYPES), country=country, limit=limit)
        resp = self.session.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=90,
        )
        if resp.status_code != 200:
            log.error("Wikidata SPARQL returned HTTP %s", resp.status_code)
            return
        rows = resp.json()["results"]["bindings"]
        log.info("Wikidata: %d organisations for %s", len(rows), COUNTRY_LABELS.get(country, country))

        for row in rows:
            def get(key: str) -> str | None:
                return row.get(key, {}).get("value")

            email = get("mail")
            if email:
                email = email.removeprefix("mailto:")
            qid = (get("org") or "").rsplit("/", 1)[-1]
            description = get("description")
            yield Lead(
                name=get("orgLabel") or "",
                source=self.name,
                source_url=ENTITY_URL.format(qid=qid),
                category=(get("kind") or "organisation").capitalize(),
                website=get("site"),
                email=email,
                email_status="found" if email else "missing",
                location=get("hq"),
                country=COUNTRY_LABELS.get(country),
                description=description[0].upper() + description[1:] if description else None,
            )
