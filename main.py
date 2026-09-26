"""Lead Generation Automation - command line entry point.

Examples
--------
python main.py                          # all sources, Excel output
python main.py --sources wikipedia      # single source
python main.py --sources wikipedia,wikidata,propublica   # add US nonprofits (IRS data)
python main.py --limit 15 --no-enrich   # quick run, skip website visits
python main.py --gsheet                 # also push to Google Sheets
python main.py --schedule 09:00         # keep running, execute daily
"""

from __future__ import annotations

import argparse
import logging
import sys

from lead_automation.config import Settings
from lead_automation.pipeline import run
from lead_automation.sources import SOURCES

# ProPublica (US IRS data) is opt-in: it has no websites, so it dilutes the India-focused list.
DEFAULT_SOURCES = ("wikipedia", "wikidata")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect, clean and export organisation leads.")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help=f"comma separated subset of: {', '.join(SOURCES)} (default: {','.join(DEFAULT_SOURCES)})",
    )
    parser.add_argument("--limit", type=int, help="max leads per source (default from settings: 50)")
    parser.add_argument("--no-enrich", action="store_true", help="skip visiting websites for emails/LinkedIn")
    parser.add_argument("--gsheet", action="store_true", help="also upload to Google Sheets (needs credentials)")
    parser.add_argument("--schedule", metavar="HH:MM", help="run now and then every day at this time")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # Windows consoles may default to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.ERROR)  # dead domains are expected, keep output readable

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in sources if s not in SOURCES]
    if unknown:
        print(f"Unknown source(s): {', '.join(unknown)}. Available: {', '.join(SOURCES)}", file=sys.stderr)
        return 2

    settings = Settings()

    def job() -> dict:
        report = run(settings, sources, args.limit, enrich=not args.no_enrich, google_sheet=args.gsheet)
        print("\n=== Run summary ===")
        for key, value in report.items():
            print(f"{key:>24}: {value}")
        return report

    if args.schedule:
        from lead_automation.scheduler import run_daily

        try:
            run_daily(job, args.schedule)
        except KeyboardInterrupt:
            print("Scheduler stopped.")
        return 0

    job()
    return 0


if __name__ == "__main__":
    sys.exit(main())
