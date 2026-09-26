"""Core data model shared by every source, the cleaner and the exporters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Column order used in the Excel / Google Sheet output.
OUTPUT_COLUMNS = [
    "name",
    "category",
    "email",
    "email_status",
    "website",
    "linkedin",
    "location",
    "country",
    "description",
    "source",
    "source_url",
    "collected_at",
]

OUTPUT_HEADERS = {
    "name": "Name",
    "category": "Category",
    "email": "Email",
    "email_status": "Email Status",
    "website": "Website",
    "linkedin": "LinkedIn",
    "location": "Location",
    "country": "Country",
    "description": "Description",
    "source": "Source",
    "source_url": "Source URL",
    "collected_at": "Collected At (UTC)",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Lead:
    """One organisation / contact collected from a public source."""

    name: str
    source: str
    source_url: str = ""
    category: str = ""
    website: Optional[str] = None
    linkedin: Optional[str] = None
    email: Optional[str] = None
    # found      -> scraped from the organisation's own website
    # generated  -> pattern-based guess (info@domain), NOT verified
    # missing    -> no website available to derive anything from
    email_status: str = "missing"
    location: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    collected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)
