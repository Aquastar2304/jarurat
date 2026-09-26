"""Runtime settings. Everything can be overridden through environment
variables or a local ``.env`` file (see ``.env.example``)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_list(key: str, default: list[str]) -> list[str]:
    raw = os.getenv(key)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # Wikipedia categories whose member pages are treated as leads.
    wiki_categories: list[str] = field(
        default_factory=lambda: _env_list(
            "WIKI_CATEGORIES",
            [
                "Category:Health charities in India",
                "Category:Cancer organisations based in India",
                "Category:Non-profit organisations based in India",
            ],
        )
    )
    # Wikidata country QID for the SPARQL source (Q668 = India).
    wikidata_country: str = os.getenv("WIKIDATA_COUNTRY", "Q668")
    # Search terms for the ProPublica Nonprofit Explorer API.
    propublica_queries: list[str] = field(
        default_factory=lambda: _env_list(
            "PROPUBLICA_QUERIES", ["cancer care", "palliative care"]
        )
    )
    max_per_source: int = int(os.getenv("MAX_PER_SOURCE", "50"))
    request_delay: float = float(os.getenv("REQUEST_DELAY", "0.5"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "15"))
    enrich_workers: int = int(os.getenv("ENRICH_WORKERS", "8"))
    user_agent: str = os.getenv(
        "USER_AGENT",
        "LeadGenAutomation/1.0 (internship assignment; contact via GitHub)",
    )
    output_dir: Path = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")
    excel_filename: str = os.getenv("EXCEL_FILENAME", "leads.xlsx")
    # Google Sheets (optional). Requires a service-account JSON key.
    google_credentials: str | None = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    google_sheet_name: str = os.getenv("GOOGLE_SHEET_NAME", "Lead Generation Output")
    google_share_with: str | None = os.getenv("GOOGLE_SHARE_WITH")

    @property
    def excel_path(self) -> Path:
        return self.output_dir / self.excel_filename
