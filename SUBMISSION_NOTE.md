# Submission note - Python Automation Internship assignment

**Approach.** The script collects Indian NGO / health-charity leads from two public sources - the MediaWiki API plus BeautifulSoup scraping of Wikipedia infoboxes, and a Wikidata SPARQL query - then visits each organisation's website to pick up a real contact email and LinkedIn URL. When no email is published it generates the most likely address (`info@domain`) and flags it as unverified. pandas cleans the data (URL/email normalisation and validation, duplicate removal by domain and fuzzy name, explicit `N/A` for gaps) and openpyxl writes a formatted Excel workbook with a Summary sheet; an optional flag pushes the same table to Google Sheets via gspread. Bonus features: email pattern generation, three API integrations (Wikidata, MediaWiki, ProPublica Nonprofit Explorer) and scheduled runs (`--schedule`, Windows Task Scheduler script, GitHub Actions cron).

**Tools:** Python 3, requests, BeautifulSoup4/lxml, pandas, openpyxl, gspread, schedule, pytest.

**Deliverables**
- Code: this repository (`python main.py` reproduces the output in about two minutes)
- Output: `output/leads.xlsx` and `output/leads.csv` - 99 cleaned leads; 48 emails found on official websites, 35 generated from the domain (flagged unverified), 16 without a website (see the Summary sheet)
- Docs: `README.md` (usage, cleaning rules, scheduling, Google Sheets setup)
