"""
Goodreads → Skoob synchronisation loop.

Iterates through a normalised Goodreads DataFrame, searches each book on
Skoob, and sets the appropriate reading status.
"""

import random
import time
from typing import Any

import pandas as pd
from playwright.sync_api import Page
from loguru import logger

from config import (
    FAILED_BOOKS_FILE,
    GOODREADS_TO_SKOOB_SHELF,
    JITTER_MAX,
    JITTER_MIN,
    SKOOB_BTN_SELECTORS,
    SKOOB_SEARCH_URL_TEMPLATE,
)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def run(page: Page, df: pd.DataFrame) -> None:
    """
    Process every row in *df* and update book status on Skoob.

    Books that fail are collected and saved to ``FAILED_BOOKS_FILE``.
    """
    failed: list[dict[str, Any]] = []
    total = len(df)
    logger.info(f"Starting Goodreads → Skoob sync for {total} books...")

    for seq, (_, row) in enumerate(df.iterrows(), start=1):
        title: str = row.get("Title", "Unknown Title")
        author: str = row.get("Author", "Unknown Author")
        isbn: str = row.get("clean_isbn", "")
        shelf: str = row.get("Exclusive Shelf", "")
        target_status: str | None = GOODREADS_TO_SKOOB_SHELF.get(shelf)

        if not target_status:
            logger.warning(f"Skipping '{title}': unmapped shelf '{shelf}'.")
            continue

        logger.info(f"[{seq}/{total}] {title} ({author}) → {target_status}")

        try:
            found = _search_book(page, isbn, title, author)
            if not found:
                logger.error(f"Book not found on Skoob: {title}")
                failed.append(row.to_dict())
                continue

            time.sleep(1)  # let page settle

            if _set_status(page, target_status, title):
                logger.success(f"✔ '{title}' → '{target_status}'")
            else:
                logger.error(f"✘ Could not set status for '{title}'")
                failed.append(row.to_dict())

        except Exception as exc:
            logger.error(f"Unexpected error for '{title}': {exc}")
            failed.append(row.to_dict())

        _jitter()

    # Persist failures
    if failed:
        pd.DataFrame(failed).to_csv(FAILED_BOOKS_FILE, index=False)
        logger.warning(f"Done. {len(failed)} failure(s) saved to {FAILED_BOOKS_FILE}.")
    else:
        logger.success("Done — all books synced successfully!")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _search_book(page: Page, isbn: str, title: str, author: str) -> bool:
    """
    Search Skoob for a book.  Tries ISBN first, then Title + Author.

    Returns ``True`` if at least one result was found.
    """
    for label, query in [("ISBN", isbn), ("Title+Author", f"{title} {author}")]:
        if not query.strip():
            continue
        logger.debug(f"  Searching by {label}: {query}")
        page.goto(
            SKOOB_SEARCH_URL_TEMPLATE.format(query=query),
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(1500)

        if page.locator(".box_livro").count() > 0 or "livro/resenhas" in page.url:
            return True

        logger.debug(f"  No results for {label}.")

    return False


def _set_status(page: Page, target_status: str, book_title: str) -> bool:
    """
    On a search result or book-detail page, navigate to the first result and
    set the reading status.
    """
    try:
        # If still on search results, click through to the book detail page
        if "livro/lista/busca" in page.url:
            first = page.locator(".box_livro").first
            if first.count() == 0:
                return False
            first.locator("a").first.click()
            page.wait_for_load_state("domcontentloaded")

        logger.debug(f"  Setting status to '{target_status}'...")

        # Try specific Skoob button IDs
        selector = SKOOB_BTN_SELECTORS.get(target_status)
        if selector and page.locator(selector).count() > 0:
            page.locator(selector).click()
            page.wait_for_timeout(1000)
            return True

        # Fallback: click by accessible role name
        page.get_by_role("button", name=target_status).or_(
            page.get_by_role("link", name=target_status)
        ).first.click()
        page.wait_for_timeout(1000)
        return True

    except Exception as exc:
        logger.error(f"  DOM interaction failed for '{book_title}': {exc}")
        return False


def _jitter() -> None:
    """Random sleep to mimic human behaviour."""
    delay = random.uniform(JITTER_MIN, JITTER_MAX)
    logger.debug(f"  Sleeping {delay:.1f}s...")
    time.sleep(delay)
