# Goodreads ↔ Skoob Bi-Directional Sync

Sync your library between Goodreads and Skoob using Python + Playwright.

## Prerequisites

- Python 3.10+
- Google Chrome / Chromium installed.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Directions

### Goodreads → Skoob (default)

1. Export your Goodreads library at [goodreads.com/review/import](https://www.goodreads.com/review/import).
2. Save the file as `input/goodreads_library_export.csv` (create the `input/` folder if it doesn't exist).
3. Run:

```bash
python main.py --direction to-skoob
```

### Skoob → Goodreads

Scrapes your Skoob shelves and generates `skoob_export_for_goodreads.csv` which
you can upload at [goodreads.com/review/import](https://www.goodreads.com/review/import).

```bash
python main.py --direction to-goodreads
```

### Both directions

```bash
python main.py --direction both
```

> **Note:** On every run the script opens a browser window. **Log in to Skoob manually** — the script detects your session and resumes automatically.

## Shelf Mapping

| Goodreads | Skoob |
|---|---|
| `read` | Lido |
| `currently-reading` | Lendo |
| `to-read` | Quero Ler / Vou Ler |

## Error Handling

- Failed books are saved to `failed_books.csv` for manual review.
- Random delays between actions to mimic human behaviour.
- Detailed logs written to `execution.log`.
