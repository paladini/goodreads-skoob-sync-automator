"""
Goodreads → Skoob synchronisation loop.

Uses Playwright to:
  1. Type a book name in Skoob's search bar.
  2. Click on the first autocomplete dropdown result.
  3. On the book detail page, click the appropriate reading status button.
"""

import random
import time
from typing import Any

import pandas as pd
from playwright.sync_api import Page, Locator
from loguru import logger

from config import (
    FAILED_BOOKS_FILE,
    GOODREADS_TO_SKOOB_SHELF,
    JITTER_MAX,
    JITTER_MIN,
    SKOOB_BASE_URL,
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
            logger.debug(f"Skipping '{title}': unmapped shelf '{shelf}'.")
            continue

        logger.info(f"[{seq}/{total}] {title} ({author}) → {target_status}")

        try:
            found = _search_and_open_book(page, isbn, title, author)
            if not found:
                logger.error(f"Book not found on Skoob: {title}")
                failed.append(row.to_dict())
                continue

            time.sleep(1)  # let book page render

            if _set_status(page, target_status, title):
                logger.success(f"✔ '{title}' → '{target_status}'")
            else:
                logger.warning(f"⚠ Status may already be set for '{title}', skipping.")

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

def _search_and_open_book(
    page: Page, isbn: str, title: str, author: str
) -> bool:
    """
    Search for a book on Skoob using the search bar autocomplete dropdown.

    Strategy:
      1. ISBN (if available)
      2. Title + Author
      3. Title only

    Returns True if we end up on a /livro/ detail page.
    """
    queries: list[tuple[str, str]] = []
    if isbn.strip():
        queries.append(("ISBN", isbn.strip()))
    # Clean parenthetical suffixes like "(Portuguese Edition)" from title
    clean_title = _clean_title(title)
    queries.append(("Title+Author", f"{clean_title} {author}"))
    queries.append(("Title only", clean_title))

    for label, query in queries:
        logger.debug(f"  Searching by {label}: {query}")

        if _search_via_dropdown(page, query):
            return True

        logger.debug(f"  No results for {label}.")

    return False


def _clean_title(title: str) -> str:
    """Remove common Goodreads parenthetical suffixes that won't match on Skoob."""
    import re
    # e.g. "(Portuguese Edition)", "(The Foo #1)", etc.
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", title).strip()
    return cleaned if cleaned else title


def _search_via_dropdown(page: Page, query: str) -> bool:
    """
    Navigate to Skoob, type into the search bar, wait for autocomplete
    dropdown results, and click the first one.

    Returns True if we end up on a /livro/ page.
    """
    # Go to homepage to get a fresh search bar
    page.goto(SKOOB_BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # Find the search input
    search_input = _find_search_input(page)
    if not search_input:
        logger.warning("  Could not find search input on page.")
        return False

    # Type the query slowly to trigger autocomplete
    search_input.click()
    search_input.fill("")
    time.sleep(0.3)
    search_input.type(query, delay=50)  # type char-by-char to trigger autocomplete

    # Wait for autocomplete dropdown to appear
    page.wait_for_timeout(2500)

    # Try to click the first autocomplete result
    if _click_dropdown_result(page):
        # Wait for book page to load
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)

        if "/livro/" in page.url:
            logger.debug(f"  Navigated to book page: {page.url}")
            return True

    return False


def _find_search_input(page: Page) -> Locator | None:
    """Find the search input element using multiple selectors."""
    selectors = [
        "input[type='search']",
        "input[name='search']",
        "input[name='q']",
        "input[placeholder*='uscar']",     # Buscar
        "input[placeholder*='esquis']",    # Pesquisar
        "input[placeholder*='ivro']",      # livro
        "#search",
        ".search-input",
        "header input[type='text']",
        "nav input[type='text']",
        "input[type='text']",              # broad fallback
    ]

    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                logger.debug(f"  Found search input: {sel}")
                return loc.first
        except Exception:
            continue

    # Try by role
    try:
        loc = page.get_by_role("searchbox")
        if loc.count() > 0:
            return loc.first
    except Exception:
        pass

    return None


def _click_dropdown_result(page: Page) -> bool:
    """
    Click the first result in the search autocomplete dropdown.

    Skoob shows a dropdown with book cards containing title, author,
    and a link to the book detail page.
    """
    # Selectors for autocomplete dropdown results (based on Skoob's current UI)
    dropdown_selectors = [
        # Direct links inside dropdown results
        ".dropdown-menu a[href*='/livro/']",
        ".autocomplete a[href*='/livro/']",
        ".search-results a[href*='/livro/']",
        ".suggestions a[href*='/livro/']",
        # Any link to a livro page that appeared after typing
        "a[href*='/livro/']:not(nav a):not(header a):not(footer a)",
        # Generic dropdown items
        ".dropdown-item",
        ".autocomplete-item",
        ".suggestion-item",
        # The book result cards visible in the screenshot
        ".livro-capa",
        ".box_livro a",
    ]

    for sel in dropdown_selectors:
        try:
            loc = page.locator(sel)
            count = loc.count()
            if count > 0:
                # Click the first visible result
                for i in range(min(count, 3)):
                    item = loc.nth(i)
                    if item.is_visible():
                        logger.debug(f"  Clicking dropdown result via: {sel} (item {i})")
                        item.click()
                        return True
        except Exception:
            continue

    # Fallback: look for any visible link containing /livro/ that appeared
    # after the search (not in the main nav)
    try:
        livro_links = page.locator("a[href*='/livro/']")
        count = livro_links.count()
        for i in range(count):
            link = livro_links.nth(i)
            href = link.get_attribute("href") or ""
            # Skip navigation/header links, only click search results
            if "/lista/" in href or "/resenhas/" in href:
                continue
            if link.is_visible():
                box = link.bounding_box()
                # Only click results that appear below the search bar (y > 80px)
                if box and box["y"] > 80:
                    logger.debug(f"  Clicking livro link: {href}")
                    link.click()
                    return True
    except Exception:
        pass

    return False


def _set_status(page: Page, target_status: str, book_title: str) -> bool:
    """
    On a book detail page, click the reading status button.

    Skoob's book page has buttons like "Quero ler", "Relendo", "Abandonei",
    "Resenhas", plus a "Lido" checkbox or similar control.
    """
    try:
        logger.debug(f"  Setting status to '{target_status}' on {page.url}")

        # Map status labels to common button text variations on Skoob
        status_text_variants: dict[str, list[str]] = {
            "Lido": ["Lido", "lido", "Li", "li"],
            "Lendo": ["Lendo", "lendo", "Estou lendo"],
            "Quero Ler": ["Quero ler", "quero ler", "Quero Ler", "VOU LER", "Vou ler"],
        }

        texts_to_try = status_text_variants.get(target_status, [target_status])

        # Strategy 1: Click button/link by text content
        for text in texts_to_try:
            try:
                # Try exact text match on buttons
                btn = page.get_by_role("button", name=text, exact=False)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(1500)
                    logger.debug(f"  Clicked button with text: '{text}'")
                    return True
            except Exception:
                pass

            try:
                # Try links
                link = page.get_by_role("link", name=text, exact=False)
                if link.count() > 0 and link.first.is_visible():
                    link.first.click()
                    page.wait_for_timeout(1500)
                    logger.debug(f"  Clicked link with text: '{text}'")
                    return True
            except Exception:
                pass

        # Strategy 2: Try by CSS selectors with text match
        for text in texts_to_try:
            try:
                loc = page.locator(f"button:has-text('{text}'), a:has-text('{text}')")
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass

        # Strategy 3: Try common Skoob button IDs
        id_selectors = [
            "#bt_lido", "#bt_lendo", "#bt_quero",
            "#btn-lido", "#btn-lendo", "#btn-quero",
            "#btn-status-1", "#btn-status-2", "#btn-status-3",
        ]
        for sel in id_selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    page.wait_for_timeout(1500)
                    logger.debug(f"  Clicked via selector: {sel}")
                    return True
            except Exception:
                pass

        logger.warning(f"  Could not find status button for '{target_status}'")
        return False

    except Exception as exc:
        logger.error(f"  DOM interaction failed for '{book_title}': {exc}")
        return False


def _jitter() -> None:
    """Random sleep to mimic human behaviour."""
    delay = random.uniform(JITTER_MIN, JITTER_MAX)
    logger.debug(f"  Sleeping {delay:.1f}s...")
    time.sleep(delay)
