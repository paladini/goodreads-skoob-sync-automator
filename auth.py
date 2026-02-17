"""
Human-in-the-loop authentication module for Skoob.

Opens the Skoob login page in a visible browser and polls until
the user has manually completed authentication.
"""

import time
import re

from playwright.sync_api import Page
from loguru import logger

from config import SKOOB_LOGIN_URL


def wait_for_login(page: Page) -> str:
    """
    Navigate to Skoob login and block until the user has logged in manually.

    Detection heuristics (any one triggers):
      - URL contains ``/usuario/`` followed by digits.
      - URL contains ``/timeline`` or ``/atividades``.
      - DOM element ``#topo-user`` is present.

    Returns:
        The Skoob user ID extracted from the URL, or an empty string
        if the ID could not be determined.
    """
    logger.info("Navigating to Skoob login page...")
    page.goto(SKOOB_LOGIN_URL, wait_until="domcontentloaded")

    logger.info(
        "┌─────────────────────────────────────────────────────┐\n"
        "│  PLEASE LOG IN MANUALLY in the browser window.     │\n"
        "│  The script will resume automatically once logged.  │\n"
        "└─────────────────────────────────────────────────────┘"
    )

    user_id: str = ""

    while True:
        current_url = page.url

        # Check URL patterns that indicate a logged-in state
        match = re.search(r"/usuario/(\d+)", current_url)
        if match:
            user_id = match.group(1)
            logger.success(f"Login detected via URL (user_id={user_id}).")
            break

        if "/timeline" in current_url or "/atividades" in current_url:
            logger.success("Login detected via URL (timeline/atividades).")
            break

        # Check for authenticated DOM element
        try:
            if page.locator("#topo-user").count() > 0:
                logger.success("Login detected via DOM element (#topo-user).")
                break
        except Exception:
            pass

        time.sleep(1)

    # If we didn't capture the user_id from the URL, try to extract it from the page
    if not user_id:
        try:
            # Navigate to home/profile to capture user_id from URL
            page.goto("https://www.skoob.com.br/usuario/home", wait_until="domcontentloaded")
            time.sleep(2)
            match = re.search(r"/usuario/(\d+)", page.url)
            if match:
                user_id = match.group(1)
                logger.info(f"Resolved user_id={user_id} from profile redirect.")
        except Exception:
            logger.warning("Could not resolve Skoob user_id. Shelf scraping may require manual URL.")

    return user_id
