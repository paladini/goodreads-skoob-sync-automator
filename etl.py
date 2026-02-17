"""
ETL helpers for CSV loading, normalization, and export generation.
"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from config import GOODREADS_EXPORT_FILE, GOODREADS_TO_SKOOB_SHELF, SKOOB_EXPORT_FILE


# ---------------------------------------------------------------------------
# Goodreads CSV → DataFrame
# ---------------------------------------------------------------------------

def load_goodreads_csv(filepath: str = GOODREADS_EXPORT_FILE) -> pd.DataFrame:
    """
    Load a Goodreads export CSV, sanitize ISBN13, and keep only relevant shelves.

    Returns:
        A filtered DataFrame with an added ``clean_isbn`` column.
    """
    path = Path(filepath)
    if not path.exists():
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    try:
        df = pd.read_csv(filepath)
    except Exception as exc:
        logger.error(f"Failed to read CSV: {exc}")
        sys.exit(1)

    for col in ("ISBN13", "Exclusive Shelf"):
        if col not in df.columns:
            logger.error(f"Required column '{col}' not found in CSV.")
            sys.exit(1)

    # Sanitize ISBN13 — Goodreads wraps values like ="1234567890123"
    df["clean_isbn"] = df["ISBN13"].apply(_clean_isbn)

    # Keep only relevant shelves
    relevant = set(GOODREADS_TO_SKOOB_SHELF.keys())
    df_filtered = df[df["Exclusive Shelf"].isin(relevant)].copy()

    logger.info(f"Loaded {len(df)} rows, filtered to {len(df_filtered)} relevant books.")
    return df_filtered


# ---------------------------------------------------------------------------
# Skoob scraped data → Goodreads import CSV
# ---------------------------------------------------------------------------

def generate_goodreads_csv(
    books: list[dict[str, Any]],
    output_path: str = SKOOB_EXPORT_FILE,
) -> Path:
    """
    Write a list of book dicts (scraped from Skoob) into a Goodreads-compatible
    import CSV.

    Expected keys per book dict (all optional except ``title``):
        title, author, isbn, my_rating, average_rating, publisher,
        binding, year_published, original_publication_year,
        date_read, date_added, shelves, bookshelves, my_review

    Returns:
        The Path to the written file.
    """
    # Column order must match the Goodreads sample template
    columns = [
        "Title",
        "Author",
        "ISBN",
        "My Rating",
        "Average Rating",
        "Publisher",
        "Binding",
        "Year Published",
        "Original Publication Year",
        "Date Read",
        "Date Added",
        "Shelves",
        "Bookshelves",
        "My Review",
    ]

    rows: list[dict[str, Any]] = []
    for book in books:
        rows.append({
            "Title": book.get("title", ""),
            "Author": book.get("author", ""),
            "ISBN": book.get("isbn", ""),
            "My Rating": book.get("my_rating", ""),
            "Average Rating": book.get("average_rating", ""),
            "Publisher": book.get("publisher", ""),
            "Binding": book.get("binding", ""),
            "Year Published": book.get("year_published", ""),
            "Original Publication Year": book.get("original_publication_year", ""),
            "Date Read": book.get("date_read", ""),
            "Date Added": book.get("date_added", ""),
            "Shelves": book.get("shelves", ""),
            "Bookshelves": book.get("bookshelves", ""),
            "My Review": book.get("my_review", ""),
        })

    df = pd.DataFrame(rows, columns=columns)
    out = Path(output_path)
    df.to_csv(out, index=False)
    logger.success(f"Exported {len(df)} books to {out}")
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_isbn(val: Any) -> str:
    """Remove non-numeric characters from an ISBN field."""
    if pd.isna(val):
        return ""
    return "".join(filter(str.isdigit, str(val)))
