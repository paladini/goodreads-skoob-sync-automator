"""
Configuration constants, URLs, and shelf mappings for the Goodreads ↔ Skoob sync.
"""

# --- File paths ---
GOODREADS_EXPORT_FILE: str = "goodreads_library_export.csv"
FAILED_BOOKS_FILE: str = "failed_books.csv"
SKOOB_EXPORT_FILE: str = "skoob_export_for_goodreads.csv"

# --- Skoob URLs ---
SKOOB_LOGIN_URL: str = "https://www.skoob.com.br/login"
SKOOB_SEARCH_URL_TEMPLATE: str = "https://www.skoob.com.br/livro/lista/busca:{query}"
SKOOB_SHELF_URL_TEMPLATE: str = "https://www.skoob.com.br/usuario/{user_id}/estante/tipo/{status_id}/page:{page}"

# --- Goodreads shelf → Skoob status (for Goodreads → Skoob) ---
GOODREADS_TO_SKOOB_SHELF: dict[str, str] = {
    "read": "Lido",
    "currently-reading": "Lendo",
    "to-read": "Vou Ler",
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
    "Vou Ler": "to-read",
}

# --- Skoob button ID selectors (for setting status on book detail page) ---
SKOOB_BTN_SELECTORS: dict[str, str] = {
    "Lido": "#bt_lido",
    "Lendo": "#bt_lendo",
    "Vou Ler": "#bt_quero",
}

# --- Timing ---
JITTER_MIN: float = 2.5
JITTER_MAX: float = 5.0
