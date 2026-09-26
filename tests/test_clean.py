import pandas as pd

from lead_automation.clean import clean_leads, leads_to_frame, name_key, normalize_email, normalize_url
from lead_automation.models import Lead


def _lead(**kwargs) -> Lead:
    base = dict(name="Org", source="test", source_url="https://example.org/src")
    base.update(kwargs)
    return Lead(**base)


def test_normalize_url_adds_scheme_lowercases_host_and_strips_slash():
    assert normalize_url("WWW.Example.ORG/") == "http://www.example.org"
    assert normalize_url("https://Example.org/Path/") == "https://example.org/Path"
    assert normalize_url("  ") is None
    assert normalize_url(None) is None


def test_normalize_email_validates_and_lowercases():
    assert normalize_email(" Info@Example.ORG ") == "info@example.org"
    assert normalize_email("not-an-email") is None
    assert normalize_email(float("nan")) is None


def test_name_key_ignores_case_punctuation_and_legal_suffix():
    assert name_key("Hope Foundation") == name_key("HOPE foundation.")
    assert name_key("Cancer-Care, Inc.") == name_key("cancer care")


def test_clean_removes_duplicates_and_fills_missing_values():
    leads = [
        _lead(name="Hope Foundation", website="https://hope.org", email="info@hope.org", email_status="found"),
        _lead(name="HOPE Foundation", website="http://www.hope.org/"),  # duplicate domain, less complete
        _lead(name="Care Trust", location="Mumbai"),
        _lead(name="care trust", website="https://caretrust.in", location="Pune"),  # duplicate name, more complete
        _lead(name="", website="https://nameless.org"),  # no name -> dropped
        _lead(name="Bad Mail", email="broken@", email_status="found"),
    ]
    df, report = clean_leads(leads_to_frame(leads))

    assert report["input_rows"] == 6
    assert report["removed_no_name"] == 1
    assert report["removed_duplicates"] == 2
    assert report["output_rows"] == 3
    assert report["invalid_emails_dropped"] == 1

    rows = df.set_index("name")
    assert rows.loc["Hope Foundation", "email"] == "info@hope.org"
    assert rows.loc["care trust", "website"] == "https://caretrust.in"  # most complete row kept
    assert rows.loc["Bad Mail", "email"] == "N/A"
    assert rows.loc["Bad Mail", "email_status"] == "missing"
    assert not df.isna().any().any()  # no blank cells in the output
    assert list(df["name"]) == sorted(df["name"], key=str.lower)


def test_leads_to_frame_has_every_output_column():
    df = leads_to_frame([_lead()])
    assert isinstance(df, pd.DataFrame)
    assert "collected_at" in df.columns and "linkedin" in df.columns
