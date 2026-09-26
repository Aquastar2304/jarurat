"""Data cleaning with pandas: normalisation, validation, de-duplication and
missing-value handling. Returns the cleaned frame plus a report used for
the summary sheet and the console."""

from __future__ import annotations

import logging
import re

import pandas as pd

from .enrich import EMAIL_RE, domain_of
from .models import OUTPUT_COLUMNS, Lead

log = logging.getLogger(__name__)

MISSING = "N/A"
TEXT_COLUMNS = ("name", "category", "location", "country", "description", "source", "source_url")
_NAME_NOISE = re.compile(r"[^a-z0-9]+")
_LEGAL_SUFFIX = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|foundation|trust|society|corp|corporation|co)\b\.?"
)


def leads_to_frame(leads: list[Lead]) -> pd.DataFrame:
    df = pd.DataFrame([lead.to_dict() for lead in leads])
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[OUTPUT_COLUMNS]


# ---- normalisers ---------------------------------------------------------
def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_text(value) -> str | None:
    if _is_missing(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip(" ,; ")
    return text or None


def normalize_url(value) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    if not re.match(r"^https?://", text, re.I):
        text = "http://" + text
    scheme, rest = text.split("://", 1)
    host, _, path = rest.partition("/")
    url = f"{scheme.lower()}://{host.lower()}"
    if path:
        url += "/" + path
    return url.rstrip("/")


def normalize_email(value) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    text = text.lower()
    return text if EMAIL_RE.fullmatch(text) else None


def name_key(value) -> str:
    """Loose key for duplicate detection: case/punctuation/legal-suffix insensitive."""
    text = (normalize_text(value) or "").lower()
    text = _LEGAL_SUFFIX.sub("", text)
    return _NAME_NOISE.sub("", text)


# ---- main entry point ----------------------------------------------------
def clean_leads(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report: dict[str, int | str] = {"input_rows": int(len(df))}
    df = df.copy().astype(object)

    for col in TEXT_COLUMNS:
        df[col] = df[col].map(normalize_text)
    df["website"] = df["website"].map(normalize_url)
    df["linkedin"] = df["linkedin"].map(normalize_url)
    raw_emails = df["email"].map(normalize_text)
    df["email"] = df["email"].map(normalize_email)
    invalid_emails = int((raw_emails.notna() & df["email"].isna()).sum())
    df.loc[df["email"].isna(), "email_status"] = "missing"

    # Rows without a name are unusable.
    before = len(df)
    df = df[df["name"].notna()]
    report["removed_no_name"] = int(before - len(df))

    # De-duplicate: same website domain, then same normalised name.
    # Rows with more filled fields win.
    df = df.assign(
        _completeness=df[["email", "website", "linkedin", "location"]].notna().sum(axis=1),
        _domain=df["website"].map(domain_of),
        _name_key=df["name"].map(name_key),
    ).sort_values("_completeness", ascending=False)
    before = len(df)
    df = df[~(df["_domain"].notna() & df.duplicated("_domain"))]
    df = df[~df.duplicated("_name_key")]
    report["removed_duplicates"] = int(before - len(df))
    df = (
        df.drop(columns=["_completeness", "_domain", "_name_key"])
        .sort_values("name", key=lambda s: s.str.lower())
        .reset_index(drop=True)
    )

    report.update(
        {
            "invalid_emails_dropped": invalid_emails,
            "output_rows": int(len(df)),
            "emails_found": int((df["email_status"] == "found").sum()),
            "emails_generated": int(df["email_status"].astype(str).str.startswith("generated").sum()),
            "missing_email": int(df["email"].isna().sum()),
            "missing_website": int(df["website"].isna().sum()),
            "missing_linkedin": int(df["linkedin"].isna().sum()),
            "missing_location": int(df["location"].isna().sum()),
        }
    )

    # Missing values are made explicit so the sheet has no blank cells.
    df = df.where(df.notna(), MISSING)
    log.info(
        "Cleaning: %d -> %d rows (%d duplicates, %d without name removed)",
        report["input_rows"], report["output_rows"], report["removed_duplicates"], report["removed_no_name"],
    )
    return df, report
