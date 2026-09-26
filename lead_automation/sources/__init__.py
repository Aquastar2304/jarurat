"""Source registry. Add a new source by implementing ``LeadSource`` and
registering it here; the pipeline and CLI pick it up automatically."""

from __future__ import annotations

from .base import LeadSource
from .propublica import ProPublicaSource
from .wikidata import WikidataSource
from .wikipedia import WikipediaSource

SOURCES: dict[str, type[LeadSource]] = {
    WikipediaSource.name: WikipediaSource,
    WikidataSource.name: WikidataSource,
    ProPublicaSource.name: ProPublicaSource,
}

__all__ = ["LeadSource", "SOURCES", "WikipediaSource", "WikidataSource", "ProPublicaSource"]
