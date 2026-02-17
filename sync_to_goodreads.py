"""
Skoob → Goodreads synchronisation.

Scrapes the authenticated user's Skoob shelves and generates a
Goodreads-compatible import CSV.
"""

import random
import re
import time
from typing import Any

from playwright.sync_api import Page
from loguru import logger

from config import (
    JITTER_MAX,
    JITTER_MIN,
    SKOOB_STATUS_IDS,
    SKOOB_TO_GOODREADS_SHELF,
)
from etl import generate_goodreads_csv


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def run(page: Page, user_id: str) -> None:
    """
    Scrape all Skoob shelves for *user_id* and export a Goodreads CSV.
    """
    if not user_id:
        logger.error(
            "No Skoob user_id available. Cannot scrape shelves.\n"
            "Tip: after login, navigate to your profile so the script "
            "can capture your user_id from the URL."
        )
        return

    all_books: list[dict[str, Any]] = []

    # Iterate through each shelf type we care about
    for status_id, status_label in SKOOB_STATUS_IDS.items():
        goodreads_shelf = SKOOB_TO_GOODREADS_SHELF.get(status_label)
        if not goodreads_shelf:
            logger.debug(f"Skipping Skoob shelf '{status_label}' (no Goodreads mapping).")
            continue

        logger.info(f"Scraping shelf: {status_label} (status_id={status_id}) → Goodreads '{goodreads_shelf}'")
        books = _scrape_shelf(page, user_id, status_id, status_label, goodreads_shelf)
        all_books.extend(books)

    if all_books:
        generate_goodreads_csv(all_books)
    else:
        logger.warning("No books found on any Skoob shelf.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _scrape_shelf(
    page: Page,
    user_id: str,
    status_id: int,
    status_label: str,
    goodreads_shelf: str,
) -> list[dict[str, Any]]:
    """
    Paginate through a single Skoob shelf and extract book data.
    """
    books: list[dict[str, Any]] = []
    current_page = 1

    while True:
        url = f"https://www.skoob.com.br/usuario/{user_id}/estante/tipo/{status_id}/page:{current_page}"
        logger.debug(f"  Loading page {current_page}: {url}")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Collect book cards
        cards = page.locator(".box_livro")
        count = cards.count()

        if count == 0:
            if current_page == 1:
                logger.info(f"  Shelf '{status_label}' is empty.")
            else:
                logger.debug(f"  No more books on page {current_page}.")
            break

        logger.info(f"  Found {count} books on page {current_page}.")

        for i in range(count):
            card = cards.nth(i)
            book = _extract_book_from_card(card, goodreads_shelf)
            if book:
                books.append(book)

        # Check if there is a next page
        # Skoob typically uses a pagination bar; if no "next" link, we stop
        next_btn = page.locator("a.next, a[rel='next'], .pagination .next a")
        if next_btn.count() == 0:
            logger.debug("  No next-page link found — end of shelf.")
            break

        current_page += 1
        _jitter()

    logger.info(f"  Total from '{status_label}': {len(books)} books.")
    return books


def _extract_book_from_card(card: Any, goodreads_shelf: str) -> dict[str, Any] | None:
    """
    Extract basic book metadata from a Skoob search/shelf card element.
    """
    try:
        # Title — usually an anchor or heading inside the card
        title_el = card.locator("a[title], .box_livro__titulo, h2, h3").first
        title = title_el.get_attribute("title") or title_el.inner_text()
        title = title.strip()

        # Author — usually in a secondary line
        author = ""
        author_el = card.locator(".box_livro__autor, .autor, span.by a")
        if author_el.count() > 0:
            author = author_el.first.inner_text().strip()

        # Rating — user rating if visible on the card
        my_rating = ""
        rating_el = card.locator("[data-nota], .rating .star.active, .estrelas .ativa")
        if rating_el.count() > 0:
            # Try data attribute first
            nota = rating_el.first.get_attribute("data-nota")
            if nota:
                my_rating = nota
            else:
                my_rating = str(rating_el.count())

        return {
            "title": title,
            "author": author,
            "isbn": "",  # ISBN is rarely visible on shelf cards
            "my_rating": my_rating,
            "average_rating": "",
            "publisher": "",
            "binding": "",
            "year_published": "",
            "original_publication_year": "",
            "date_read": "",
            "date_added": "",
            "shelves": goodreads_shelf,
            "bookshelves": "",
            "my_review": "",
        }
    except Exception as exc:
        logger.warning(f"  Failed to extract book from card: {exc}")
        return None


def _jitter() -> None:
    """Random sleep to mimic human behaviour."""
    delay = random.uniform(JITTER_MIN, JITTER_MAX)
    logger.debug(f"  Sleeping {delay:.1f}s...")
    time.sleep(delay)
