"""
Skoob → Goodreads synchronisation.

Scrapes the authenticated user's Skoob shelves using the v1 JSON API
and produces a Goodreads-compatible CSV via ``etl.generate_goodreads_csv``.
"""

import time
import json
from typing import Any

from playwright.sync_api import Page
from loguru import logger

from config import (
    SKOOB_STATUS_IDS,
    SKOOB_TO_GOODREADS_SHELF,
    SKOOB_V1_BOOKCASE_URL,
    JITTER_MIN,
    JITTER_MAX,
)
from etl import generate_goodreads_csv

import random

# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def run(page: Page, user_id: str) -> None:
    """
    Read books from Skoob shelves and generate a Goodreads-compatible CSV.
    """
    if not user_id:
        logger.error("No Skoob user_id available. Cannot scrape shelves.")
        logger.info("Please pass your numeric Skoob user ID manually.")
        return

    all_books: list[dict[str, Any]] = []

    for status_id, status_label in SKOOB_STATUS_IDS.items():
        goodreads_shelf = SKOOB_TO_GOODREADS_SHELF.get(status_label)
        if not goodreads_shelf:
            logger.debug(f"Skipping Skoob shelf '{status_label}' (no Goodreads mapping).")
            continue

        logger.info(f"Scraping Skoob shelf: {status_label} (id={status_id})...")
        books = _scrape_shelf_via_api(page, user_id, status_id, status_label, goodreads_shelf)
        all_books.extend(books)
        logger.info(f"  Found {len(books)} books in '{status_label}'.")

    if all_books:
        generate_goodreads_csv(all_books)
    else:
        logger.warning("No books found on Skoob shelves.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _scrape_shelf_via_api(
    page: Page,
    user_id: str,
    status_id: int,
    status_label: str,
    goodreads_shelf: str,
) -> list[dict[str, Any]]:
    """
    Scrape all books from a Skoob shelf using the v1 JSON API.

    Uses Playwright to make requests with the authenticated session cookies.
    The API endpoint returns JSON with pagination.
    """
    books: list[dict[str, Any]] = []
    current_page = 1
    limit = 50

    while True:
        url = SKOOB_V1_BOOKCASE_URL.format(
            user_id=user_id,
            shelf_id=status_id,
            page=current_page,
            limit=limit,
        )

        logger.debug(f"  Fetching: {url}")

        try:
            # Use Playwright to make the request with session cookies
            response = page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # Try to parse the page content as JSON
            content = page.inner_text("body")
            if not content or content.strip() == "":
                logger.debug(f"  Empty response on page {current_page}, stopping.")
                break

            data = json.loads(content)
            response_list = data.get("response", [])

            if not response_list:
                logger.debug(f"  No more books on page {current_page}.")
                break

            for item in response_list:
                book = _parse_api_book(item, goodreads_shelf, status_label)
                if book:
                    books.append(book)

            logger.debug(f"  Page {current_page}: {len(response_list)} books.")

            # Check if there are more pages
            paging = data.get("paging", {})
            total_pages = paging.get("total_pages", 1) if paging else 1
            if current_page >= total_pages:
                break

            current_page += 1
            _jitter()

        except json.JSONDecodeError:
            logger.warning(f"  Could not parse JSON on page {current_page}. "
                          "Skoob may require different auth or the API has changed.")
            break
        except Exception as exc:
            logger.error(f"  Error fetching shelf page {current_page}: {exc}")
            break

    return books


def _parse_api_book(
    item: dict[str, Any],
    goodreads_shelf: str,
    status_label: str,
) -> dict[str, Any] | None:
    """Parse a book item from the Skoob v1 API response."""
    try:
        edicao = item.get("edicao", {})
        if not edicao:
            return None

        title = (
            edicao.get("nome_portugues")
            or edicao.get("titulo")
            or edicao.get("nome")
            or ""
        )
        author = edicao.get("autor") or ""
        isbn = edicao.get("isbn") or ""

        # Rating from the user's review
        my_rating = str(item.get("rating", 0) or 0)

        # Date read
        date_read = item.get("dt_leitura") or ""

        return {
            "title": title.strip(),
            "author": author.strip(),
            "isbn": isbn.strip(),
            "my_rating": my_rating,
            "shelf": goodreads_shelf,
            "date_read": date_read,
        }
    except Exception as exc:
        logger.warning(f"  Failed to parse book: {exc}")
        return None


def _jitter() -> None:
    """Random sleep to mimic human behaviour."""
    delay = random.uniform(JITTER_MIN, JITTER_MAX)
    time.sleep(delay)
