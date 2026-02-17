"""
Goodreads ↔ Skoob bi-directional sync — CLI entrypoint.

Usage:
    python main.py --direction to-skoob      # Goodreads → Skoob (default)
    python main.py --direction to-goodreads   # Skoob → Goodreads
    python main.py --direction both           # Run both flows
"""

import argparse
import sys

from playwright.sync_api import sync_playwright
from loguru import logger

from config import GOODREADS_EXPORT_FILE
from auth import wait_for_login
from etl import load_goodreads_csv
import sync_to_skoob
import sync_to_goodreads


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Bi-directional Goodreads ↔ Skoob library sync.",
    )
    parser.add_argument(
        "--direction",
        choices=["to-skoob", "to-goodreads", "both"],
        default="to-skoob",
        help=(
            "Sync direction. "
            "'to-skoob' imports from Goodreads CSV into Skoob. "
            "'to-goodreads' scrapes Skoob shelves and exports a Goodreads CSV. "
            "'both' runs both flows sequentially. (default: to-skoob)"
        ),
    )
    parser.add_argument(
        "--csv",
        default=GOODREADS_EXPORT_FILE,
        help=f"Path to the Goodreads export CSV (default: {GOODREADS_EXPORT_FILE}).",
    )
    return parser.parse_args()


def main() -> None:
    """Application entrypoint."""
    args = parse_args()
    direction: str = args.direction

    logger.info(f"Direction: {direction}")

    # Pre-flight check: if we need the Goodreads CSV, make sure it exists
    needs_csv = direction in ("to-skoob", "both")
    if needs_csv:
        from pathlib import Path

        if not Path(args.csv).exists():
            logger.error(
                f"Goodreads export CSV not found: {args.csv}\n"
                "Place your export file in this directory or pass --csv <path>."
            )
            sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Authenticate (always required)
        user_id = wait_for_login(page)

        # --- Goodreads → Skoob ---
        if direction in ("to-skoob", "both"):
            logger.info("═══ Goodreads → Skoob ═══")
            df = load_goodreads_csv(args.csv)
            sync_to_skoob.run(page, df)

        # --- Skoob → Goodreads ---
        if direction in ("to-goodreads", "both"):
            logger.info("═══ Skoob → Goodreads ═══")
            sync_to_goodreads.run(page, user_id)

        browser.close()

    logger.info("All done. 🎉")


if __name__ == "__main__":
    logger.add("execution.log", rotation="10 MB")
    main()
