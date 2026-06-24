"""
Download NYT front page PDFs.

NYT publishes a public PDF of each day's front page; no subscription required.
Files are saved to frontpages/YYYY-MM-DD.pdf and existing files are skipped,
so the download is safe to resume if interrupted.

Usage:
    download-frontpages                          # today only
    download-frontpages 2025-01-01               # one date only
    download-frontpages 2025-01-01 2025-03-06    # a date range
    download-frontpages --out-dir frontpages
"""

import argparse
import os
import random
import time
from datetime import date, timedelta

import requests

from ._cli import default_to_today

DEFAULT_OUTPUT_DIR = "frontpages"
SYNTAX = "download-frontpages [START_DATE] [END_DATE]   (dates as YYYY-MM-DD)"


def url_for_date(d: date) -> str:
    return f"https://static01.nyt.com/images/{d.year}/{d.month:02d}/{d.day:02d}/nytfrontpage/scan.pdf"


def dates_in_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def download_range(start: date, end: date, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    all_dates = list(dates_in_range(start, end))
    total = len(all_dates)

    for i, d in enumerate(all_dates, 1):
        filename = os.path.join(out_dir, f"{d.isoformat()}.pdf")

        if os.path.exists(filename):
            print(f"[{i}/{total}] {d} - already exists, skipping")
            continue

        url = url_for_date(d)
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(response.content)
                print(f"[{i}/{total}] {d} - downloaded ({len(response.content) // 1024} KB)")
            elif response.status_code == 404:
                print(f"[{i}/{total}] {d} - not found (404), skipping")
            else:
                print(f"[{i}/{total}] {d} - unexpected status {response.status_code}, skipping")
        except requests.RequestException as e:
            print(f"[{i}/{total}] {d} - error: {e}")

        # Randomized delay to be polite to the server.
        delay = random.uniform(2, 4)
        print(f"  sleeping {delay:.1f}s...")
        time.sleep(delay)

    print("Done.")


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download NYT front page PDFs. Downloads a single date unless an "
                    "end date is given; defaults to today when no date is given.",
        epilog="Examples:\n"
               "  download-frontpages                          # today only\n"
               "  download-frontpages 2025-01-01               # one date only\n"
               "  download-frontpages 2025-01-01 2025-03-06    # a date range\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("start", nargs="?", type=_parse_date,
                        help="Start date YYYY-MM-DD (default: today)")
    parser.add_argument("end", nargs="?", type=_parse_date,
                        help="End date YYYY-MM-DD. Omit to download only the start date.")
    parser.add_argument("--out-dir", default=DEFAULT_OUTPUT_DIR,
                        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    args = parser.parse_args()

    if args.start is None:
        start = date.fromisoformat(default_to_today(SYNTAX))
    else:
        start = args.start

    # A single date unless an explicit end is given.
    end = args.end if args.end is not None else start

    if end < start:
        parser.error(f"end date {end} is before start date {start}")

    download_range(start, end, args.out_dir)


if __name__ == "__main__":
    main()
