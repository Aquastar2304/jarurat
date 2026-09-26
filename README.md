# Lead Generation Automation

Python automation that collects organisation leads (NGOs, charities, health
non-profits) from public sources, enriches them with contact details, cleans
the data and writes a ready-to-use Excel workbook (and optionally a Google
Sheet). Built for the Jarurat Care Foundation *Python Automation Internship*
assignment.

```
sources  ->  enrich (emails / LinkedIn)  ->  clean (pandas)  ->  Excel / CSV / Google Sheet
```

## What it does

| Requirement | How it is met |
|---|---|
| Collect 20-30+ entries | ~100 leads per run from two Indian NGO sources (configurable, any country) |
| Name, Email, Website/LinkedIn, Location | All present; plus Category, Country, Description, Source, Source URL, timestamp |
| Store in Excel / Google Sheet automatically | `output/leads.xlsx` (formatted, hyperlinks, colour-coded email status, Summary sheet), `output/leads.csv`, optional Google Sheets push |
| Data cleaning | URL/email normalisation and validation, duplicate removal by website domain and by fuzzy name, explicit `N/A` for missing values |
| Bonus: email format generation | `info@domain` etc. derived from the website when nothing is published; flagged `generated (unverified)`; person-name patterns supported too |
| Bonus: API integration | Wikidata SPARQL API, MediaWiki API, ProPublica Nonprofit Explorer REST API |
| Bonus: scheduled run | `--schedule HH:MM` in-process scheduler, Windows Task Scheduler script, GitHub Actions cron workflow |

## Data sources

| Source | Type | Fields it contributes |
|---|---|---|
| **Wikipedia** (default) | MediaWiki API for category members + BeautifulSoup scrape of each page's infobox and External links | name, website, headquarters/location, description |
| **Wikidata** (default) | One SPARQL query over structured data | name, website, published email, headquarters, type, description |
| **ProPublica Nonprofit Explorer** (opt-in) | REST API over US IRS filings | name, city/state, NTEE category (no websites, hence opt-in) |

Every lead with a website is then **enriched**: the home page and common
contact pages are visited to pick up a real email address (`mailto:` links or
plain text) and a LinkedIn company URL. Addresses on the organisation's own
domain and generic mailboxes (`info@`, `contact@`) are preferred.

## Quick start

```bash
pip install -r requirements.txt
python main.py                 # Wikipedia + Wikidata, ~100 leads, ~2 minutes
```

Output lands in `output/leads.xlsx` and `output/leads.csv`; a run summary is
printed at the end and stored in the workbook's *Summary* sheet.

More options:

```bash
python main.py --limit 15 --no-enrich                    # quick run, no website visits
python main.py --sources wikipedia,wikidata,propublica   # add US nonprofits
python main.py --gsheet                                  # also push to Google Sheets
python main.py --schedule 09:00                          # run now, then daily at 09:00
python -m pytest                                         # unit tests (cleaning + email logic)
```

All defaults (categories, country, limits, request delay, output path,
Google credentials) can be changed in a `.env` file; see `.env.example`.

## Output columns

Name, Category, Email, Email Status (`found` / `generated (unverified)` /
`missing`), Website, LinkedIn, Location, Country, Description, Source,
Source URL, Collected At (UTC).

Email Status is colour-coded in Excel so a user can immediately tell which
addresses were actually published by the organisation and which are pattern
guesses that should be verified before outreach.

## Cleaning rules

* whitespace, citation markers and map coordinates stripped from text fields
* URLs normalised (scheme added, host lower-cased, trailing slash removed)
* emails lower-cased and validated against an RFC-style pattern; invalid ones dropped
* duplicates removed by website domain (`www.` ignored), then by normalised name
  (case, punctuation and legal suffixes such as *Foundation*/*Trust*/*Inc* ignored);
  the most complete record of each duplicate group is kept
* rows without a name are discarded; remaining blanks become `N/A`
* rows sorted alphabetically

## Google Sheets

1. Create a Google Cloud service account, enable the Sheets and Drive APIs and download its JSON key.
2. Set `GOOGLE_SERVICE_ACCOUNT_JSON=path/to/key.json` (and optionally
   `GOOGLE_SHEET_NAME`, `GOOGLE_SHARE_WITH=you@example.com`) in `.env`.
3. Run `python main.py --gsheet`. The sheet is created if it does not exist and
   its *Leads* tab is replaced on every run.

## Scheduling

* **In-process:** `python main.py --schedule 09:00` keeps running and executes daily.
* **Windows Task Scheduler:** `.\scripts\register_windows_task.ps1 -At 09:00`.
* **GitHub Actions:** `.github/workflows/scheduled-run.yml` runs the tests and
  the pipeline every Monday (or on demand) and uploads the Excel/CSV as an artifact.

## Project layout

```
main.py                     CLI entry point
lead_automation/
  config.py                 settings (env / .env)
  models.py                 Lead dataclass + output schema
  http_client.py            polite session: user-agent, retries, per-host delay
  sources/                  one module per source, registered in __init__.py
    wikipedia.py            MediaWiki API + infobox scraping
    wikidata.py             SPARQL API
    propublica.py           ProPublica REST API
  enrich.py                 email / LinkedIn discovery, email pattern generation
  clean.py                  pandas cleaning + report
  export/excel.py           formatted workbook + CSV
  export/gsheets.py         gspread upload
  pipeline.py               collect -> enrich -> clean -> export
  scheduler.py              daily in-process trigger
tests/                      pytest unit tests
scripts/                    Task Scheduler registration
output/                     leads.xlsx, leads.csv
```

Adding a new source means writing one class with a `fetch(limit)` generator
and adding it to the registry; everything downstream is source-agnostic.

## Responsible scraping

The client identifies itself with a descriptive User-Agent, waits between
requests to the same host, retries transient errors with back-off and only
reads public pages (Wikipedia, Wikidata, organisations' own contact pages).
Generated emails are clearly labelled as unverified.
