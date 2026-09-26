"""Optional Google Sheets export via gspread + a service account.

Setup (one time):
1. Create a Google Cloud service account, enable the *Google Sheets API*
   and *Google Drive API*, download its JSON key.
2. Put the key path in ``GOOGLE_SERVICE_ACCOUNT_JSON`` (see .env.example).
3. Either share an existing sheet named ``GOOGLE_SHEET_NAME`` with the
   service-account email, or let the script create it and set
   ``GOOGLE_SHARE_WITH`` to your own email so you can open it.
"""

from __future__ import annotations

import logging

import pandas as pd

from ..models import OUTPUT_COLUMNS, OUTPUT_HEADERS

log = logging.getLogger(__name__)


def push_to_google_sheet(
    df: pd.DataFrame,
    credentials_path: str,
    sheet_name: str,
    share_with: str | None = None,
    worksheet_title: str = "Leads",
) -> str:
    """Replace the *Leads* worksheet content with ``df``; returns the sheet URL."""
    import gspread  # imported lazily so the package stays optional

    client = gspread.service_account(filename=credentials_path)
    try:
        spreadsheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(sheet_name)
        if share_with:
            spreadsheet.share(share_with, perm_type="user", role="writer")
        log.info("Created Google Sheet '%s'", sheet_name)

    try:
        ws = spreadsheet.worksheet(worksheet_title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(worksheet_title, rows=len(df) + 10, cols=len(OUTPUT_COLUMNS))

    header = [OUTPUT_HEADERS[c] for c in OUTPUT_COLUMNS]
    rows = df[OUTPUT_COLUMNS].astype(str).values.tolist()
    ws.update([header] + rows, value_input_option="RAW")
    ws.format("1:1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    log.info("Pushed %d rows to Google Sheet: %s", len(rows), spreadsheet.url)
    return spreadsheet.url
