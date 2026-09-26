"""Orchestrates: collect -> enrich -> clean -> export."""

from __future__ import annotations

import logging
import time

from .clean import clean_leads, leads_to_frame
from .config import Settings
from .enrich import enrich_leads, guess_email
from .export import push_to_google_sheet, write_excel
from .http_client import PoliteSession
from .models import Lead
from .sources import SOURCES

log = logging.getLogger(__name__)


def collect(settings: Settings, source_names: list[str], limit: int, session: PoliteSession) -> list[Lead]:
    leads: list[Lead] = []
    for name in source_names:
        started = time.perf_counter()
        source_leads = list(SOURCES[name](session, settings).fetch(limit))
        log.info("%s: collected %d leads in %.1fs", name, len(source_leads), time.perf_counter() - started)
        leads.extend(source_leads)
    return leads


def run(
    settings: Settings,
    source_names: list[str] | None = None,
    limit: int | None = None,
    enrich: bool = True,
    google_sheet: bool = False,
) -> dict:
    """Run the full pipeline once and return the cleaning report."""
    source_names = source_names or list(SOURCES)
    limit = limit or settings.max_per_source
    session = PoliteSession(settings.user_agent, settings.request_delay, settings.request_timeout)
    started = time.perf_counter()

    leads = collect(settings, source_names, limit, session)
    if not leads:
        raise RuntimeError("No leads collected - check network access and source settings.")

    if enrich:
        enrich_leads(leads, session, workers=settings.enrich_workers)
    else:
        for lead in leads:
            guess_email(lead)

    df, report = clean_leads(leads_to_frame(leads))
    report["sources"] = ", ".join(source_names)
    report["runtime_seconds"] = round(time.perf_counter() - started, 1)

    excel_path = write_excel(df, report, settings.excel_path)
    report["excel_file"] = str(excel_path)

    if google_sheet:
        if not settings.google_credentials:
            log.error("Google Sheets export requested but GOOGLE_SERVICE_ACCOUNT_JSON is not set - skipped.")
        else:
            report["google_sheet_url"] = push_to_google_sheet(
                df, settings.google_credentials, settings.google_sheet_name, settings.google_share_with
            )
    return report
