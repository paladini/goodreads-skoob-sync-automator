"""
Network reconnaissance script for Skoob.

Opens Skoob in a visible browser, lets you log in, and then captures
ALL network requests/responses while you manually:
  1. Search for a book
  2. Add it to "Lido" (or any shelf)

The captured API calls are saved to 'skoob_api_calls.json' so we can
replicate them in the sync script.

Usage:
    python recon_skoob.py
"""

import json
import time
from playwright.sync_api import sync_playwright


def main() -> None:
    captured: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # --- Capture all network requests ---
        def on_request(request):
            # Only capture API-like requests (XHR, fetch, not images/css)
            resource = request.resource_type
            if resource in ("xhr", "fetch", "document"):
                entry = {
                    "method": request.method,
                    "url": request.url,
                    "resource_type": resource,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                }
                captured.append(entry)
                print(f"  >> {request.method} {request.url}")

        def on_response(response):
            url = response.url
            # Only log interesting API responses
            if any(kw in url for kw in ["/v1/", "/api/", "/search", "/livro",
                                         "/bookcase", "/bookshelf", "/estante",
                                         "/user/", "/usuario/", "status",
                                         "shelf", "rating"]):
                content_type = response.headers.get("content-type", "")
                body = ""
                try:
                    if "json" in content_type or "text" in content_type:
                        body = response.text()
                except Exception:
                    body = "<could not read body>"

                entry = {
                    "_type": "response",
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "body_preview": body[:2000] if body else "",
                }
                captured.append(entry)
                print(f"  << {response.status} {url}")
                if body and len(body) < 500:
                    print(f"     Body: {body[:300]}")

        page.on("request", on_request)
        page.on("response", on_response)

        # --- Navigate to Skoob ---
        page.goto("https://www.skoob.com.br/login", wait_until="domcontentloaded")

        print()
        print("=" * 70)
        print("  SKOOB NETWORK RECON")
        print("=" * 70)
        print()
        print("  1. LOG IN to Skoob in the browser.")
        print("  2. SEARCH for a book using the search bar.")
        print("  3. CLICK on the book result.")
        print("  4. CLICK 'Lido' (or any status button) to add it.")
        print()
        print("  All network requests are being captured.")
        print("  When done, come back here and press ENTER.")
        print()
        print("=" * 70)

        input(">>> Press ENTER when you are done (after adding a book)... ")

        # Also capture cookies for reference
        cookies = context.cookies()
        skoob_cookies = [c for c in cookies if "skoob" in c.get("domain", "")]

        browser.close()

    # --- Save captured data ---
    output = {
        "captured_requests": captured,
        "skoob_cookies": skoob_cookies,
    }

    with open("skoob_api_calls.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n✅ Captured {len(captured)} requests/responses.")
    print(f"   Saved to: skoob_api_calls.json")
    print(f"   Skoob cookies: {len(skoob_cookies)}")

    # --- Print summary of interesting calls ---
    print("\n📋 INTERESTING API CALLS:")
    print("-" * 70)
    for entry in captured:
        url = entry.get("url", "")
        if any(kw in url for kw in ["/v1/", "/api/", "search", "bookshelf",
                                     "bookcase", "estante", "status", "shelf",
                                     "livro", "rating", "book"]):
            method = entry.get("method", entry.get("_type", "?"))
            print(f"  {method:6s} {url}")
            if entry.get("post_data"):
                print(f"         POST body: {entry['post_data'][:200]}")
            if entry.get("body_preview"):
                print(f"         Response: {entry['body_preview'][:200]}")
            print()


if __name__ == "__main__":
    main()
