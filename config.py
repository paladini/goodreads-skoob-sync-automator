"""
Configuration constants, URLs, and shelf mappings for the Goodreads ↔ Skoob sync.
"""

# --- File paths ---
GOODREADS_EXPORT_FILE: str = "input/goodreads_library_export.csv"
FAILED_BOOKS_FILE: str = "failed_books.csv"
SKOOB_EXPORT_FILE: str = "skoob_export_for_goodreads.csv"

# --- Skoob URLs ---
SKOOB_LOGIN_URL: str = "https://www.skoob.com.br/login"
SKOOB_BASE_URL: str = "https://www.skoob.com.br"

# v1 JSON API for reading bookcase (uses session cookies from browser)
SKOOB_V1_BOOKCASE_URL: str = (
    "https://www.skoob.com.br/v1/bookcase/books/{user_id}"
    "/shelf_id:{shelf_id}/page:{page}/limit:{limit}/"
)

# --- Goodreads shelf → Skoob status (for Goodreads → Skoob) ---
# Only "read" is enabled for now; uncomment the others when ready.
GOODREADS_TO_SKOOB_SHELF: dict[str, str] = {
    "read": "Lido",
    # "currently-reading": "Lendo",
    # "to-read": "Quero Ler",
}

# --- Skoob status ID → shelf label ---
SKOOB_STATUS_IDS: dict[int, str] = {
    1: "Lido",
    2: "Lendo",
    3: "Quero Ler",
    5: "Abandonei",
    6: "Relendo",
}

# --- Skoob status label → Goodreads shelf (for Skoob → Goodreads) ---
SKOOB_TO_GOODREADS_SHELF: dict[str, str] = {
    "Lido": "read",
    "Lendo": "currently-reading",
    "Quero Ler": "to-read",
}

# --- Skoob status label → numeric ID for the v1 API ---
SKOOB_STATUS_LABEL_TO_ID: dict[str, int] = {
    "Lido": 1,
    "Lendo": 2,
    "Quero Ler": 3,
    "Abandonei": 5,
    "Relendo": 6,
}

# --- Timing ---
JITTER_MIN: float = 2.5
JITTER_MAX: float = 5.0
