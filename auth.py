"""
Human-in-the-loop authentication module for Skoob.

Opens the Skoob login page in a visible browser and waits for the user
to press Enter in the terminal after logging in manually.
"""

import time
import re

from playwright.sync_api import Page
from loguru import logger

from config import SKOOB_LOGIN_URL


def wait_for_login(page: Page) -> str:
    """
    Navigate to Skoob login and wait for the user to confirm login via terminal.

    The user logs in manually (password, magic link, etc.) and then
    presses **Enter** in the terminal to signal that authentication is done.

    Returns:
        The Skoob user ID extracted from the URL, or an empty string
        if the ID could not be determined.
    """
    logger.info("Navigating to Skoob login page...")
    page.goto(SKOOB_LOGIN_URL, wait_until="domcontentloaded")

    print("\n" + "=" * 60)
    print("  LOG IN TO SKOOB in the browser window.")
    print("  Use email, password, magic link — whatever works.")
    print("")
    print("  When you are logged in, come back here and press ENTER.")
    print("=" * 60)

    input("\n>>> Press ENTER after logging in to Skoob... ")

    logger.success("User confirmed login. Resuming automation.")

    # Give the page a moment to settle after login
    time.sleep(2)

    # Try to resolve the user_id
    user_id = _resolve_user_id(page)
    return user_id


def _resolve_user_id(page: Page) -> str:
    """Try to extract the Skoob user_id by navigating to the user profile."""
    try:
        page.goto("https://www.skoob.com.br/usuario/home", wait_until="domcontentloaded")
        time.sleep(2)

        match = re.search(r"/usuario/(\d+)", page.url)
        if match:
            uid = match.group(1)
            logger.info(f"Resolved user_id={uid} from profile redirect.")
            return uid

        # Try extracting from page content
        content = page.content()
        match = re.search(r'usuario[/_](\d+)', content)
        if match:
            uid = match.group(1)
            logger.info(f"Resolved user_id={uid} from page content.")
            return uid
    except Exception:
        pass

    logger.warning("Could not resolve Skoob user_id. Shelf scraping may require manual URL.")
    return ""
