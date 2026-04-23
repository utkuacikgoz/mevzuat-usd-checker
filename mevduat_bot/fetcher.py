from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from playwright.async_api import BrowserContext, Error, Page, TimeoutError, async_playwright

from .config import Settings
from .models import MevduatSnapshot

LOGGER = logging.getLogger(__name__)

CARD_SELECTOR = "#block-bistkydendeksleri"
TABLE_BODY_SELECTOR = "#table-2-9-data"
ROW_SELECTOR = f"{TABLE_BODY_SELECTOR} tr"
CURRENCY_LABEL_SELECTOR = "label.btn.btn-info.smaller-text"


class FetchError(RuntimeError):
    """Raised when the target page cannot be parsed safely."""


async def fetch_snapshot(settings: Settings, screenshot_path: Path) -> MevduatSnapshot:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Starting fetch_snapshot for currency: %s", settings.target_currency)

    async with async_playwright() as playwright:
        LOGGER.debug("Launching chromium browser (headless=%s)", settings.playwright_headless)
        browser = await playwright.chromium.launch(headless=settings.playwright_headless)
        try:
            context = await browser.new_context(
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                viewport={"width": 1600, "height": 1400},
            )
            LOGGER.debug("Browser context created")
            try:
                return await _fetch_with_context(context, settings, screenshot_path)
            finally:
                await context.close()
                LOGGER.debug("Browser context closed")
        finally:
            await browser.close()
            LOGGER.debug("Browser closed")


async def _fetch_with_context(
    context: BrowserContext,
    settings: Settings,
    screenshot_path: Path,
) -> MevduatSnapshot:
    page = await context.new_page()
    page.set_default_timeout(30_000)
    LOGGER.info("Page created, navigating to %s", settings.target_url)

    try:
        await page.goto(settings.target_url, wait_until="domcontentloaded")
        LOGGER.debug("Page loaded: domcontentloaded")
        
        await page.wait_for_load_state("networkidle")
        LOGGER.debug("Page loaded: networkidle")
        
        await _dismiss_cookie_banner(page)
        LOGGER.debug("Cookie banner dismissed")
        
        await _activate_currency(page, settings.target_currency)
        LOGGER.info("Currency %s activated", settings.target_currency)
        
        # Wait for table data to load with diagnostics
        await asyncio.sleep(2)  # Longer initial wait for table to render after currency switch
        LOGGER.debug("Waited 2s for table render after currency switch")
        
        # Check what's actually on the page
        table_body_count = await page.locator(TABLE_BODY_SELECTOR).count()
        LOGGER.debug("Table body (#%s) element count: %d", TABLE_BODY_SELECTOR.lstrip("#"), table_body_count)
        
        row_selector_use = ROW_SELECTOR
        if table_body_count == 0:
            # Try alternative selector
            alt_selector = "table tbody tr"
            alt_count = await page.locator(alt_selector).count()
            LOGGER.warning("Primary table selector found 0 elements, trying alternative '%s': %d elements", alt_selector, alt_count)
            if alt_count > 0:
                row_selector_use = alt_selector
            else:
                raise FetchError(f"No table rows found with any selector")
        
        # Get first row with diagnostics
        row = page.locator(row_selector_use).first
        row_count = await row.count()
        LOGGER.debug("First row locator count: %d", row_count)
        
        if row_count == 0:
            raise FetchError(f"No rows found in table selector: {row_selector_use}")
        
        # Try to wait for visibility with a fallback
        try:
            await row.wait_for(state="visible", timeout=5_000)
            LOGGER.debug("Table row became visible after 5s wait")
        except TimeoutError:
            LOGGER.warning("Row did not become visible within 5s, but proceeding anyway")
        
        await asyncio.sleep(1)  # Allow table to fully render
        LOGGER.debug("Waited 1s for final table render")
        
        # Verify currency is switched by checking cell content
        max_retries = 5
        cells = None
        for attempt in range(max_retries):
            try:
                cells = [text.strip() for text in await row.locator("td").all_inner_texts()]
                LOGGER.debug("Attempt %d: Got %d cells, cell[7]=%s (expected %s)", 
                            attempt + 1, len(cells), 
                            cells[7].strip() if len(cells) > 7 else "N/A", 
                            settings.target_currency)
                
                if len(cells) > 7 and cells[7].strip() == settings.target_currency:
                    LOGGER.debug("Currency match successful on attempt %d", attempt + 1)
                    break
                    
                await asyncio.sleep(0.5)
            except Exception as e:
                LOGGER.warning("Exception during cell read attempt %d: %s", attempt + 1, e)
                await asyncio.sleep(0.5)
                if attempt == max_retries - 1:
                    raise FetchError("Currency data did not load within timeout.") from e
        
        if cells is None:
            raise FetchError("Failed to extract cells after all retries")
        
        LOGGER.debug("Cell data: index_name=%s, index_code=%s, updated_at=%s, current_value=%s, daily_change=%s",
                    cells[0] if len(cells) > 0 else "N/A",
                    cells[1] if len(cells) > 1 else "N/A",
                    cells[2] if len(cells) > 2 else "N/A",
                    cells[3] if len(cells) > 3 else "N/A",
                    cells[4] if len(cells) > 4 else "N/A")
        
        if len(cells) < 6 or not cells[3].strip():
            raise FetchError("Table row is missing expected columns or current value.")

        card = page.locator(CARD_SELECTOR)
        await card.scroll_into_view_if_needed()
        LOGGER.debug("Card scrolled into view")
        
        await asyncio.sleep(0.5)
        await card.screenshot(path=str(screenshot_path))
        LOGGER.info("Screenshot saved to %s", screenshot_path)

        snapshot = MevduatSnapshot(
            index_name=_clean(cells[0]),
            index_code=_clean(cells[1]),
            updated_at=_clean(cells[2]),
            current_value=_clean(cells[3]),
            daily_change_percent=_clean(cells[4]),
            currency=settings.target_currency,
        )
        LOGGER.info("Snapshot created successfully: value=%s, currency=%s", 
                   snapshot.current_value, snapshot.currency)
        return snapshot
        
    except TimeoutError as exc:
        LOGGER.error("TimeoutError during fetch: %s", exc, exc_info=True)
        raise FetchError("Timed out while waiting for the mevduat table to load.") from exc
    except Error as exc:
        LOGGER.error("Playwright Error during fetch: %s", exc, exc_info=True)
        raise FetchError(f"Playwright failed to load the target page: {exc}") from exc
    except FetchError as exc:
        LOGGER.error("FetchError: %s", exc, exc_info=True)
        raise
    except Exception as exc:
        LOGGER.error("Unexpected error during fetch: %s", exc, exc_info=True)
        raise FetchError(f"Unexpected error: {exc}") from exc
    finally:
        await page.close()
        LOGGER.debug("Page closed")


async def _dismiss_cookie_banner(page: Page) -> None:
    LOGGER.debug("Attempting to dismiss cookie banner")
    button = page.locator("button").filter(
        has_text=re.compile(r"t[üu]m[üu]n[üu]\s+kabul\s+et", re.I)
    ).first
    count = await button.count()
    LOGGER.debug("Cookie banner button count: %d", count)
    
    if count:
        try:
            await button.click(timeout=5_000)
            LOGGER.debug("Cookie banner dismissed successfully")
        except TimeoutError:
            LOGGER.warning("Timeout dismissing cookie banner, continuing anyway")
            return
    else:
        LOGGER.debug("No cookie banner found")


async def _activate_currency(page: Page, currency: str) -> None:
    LOGGER.debug("Attempting to activate currency: %s", currency)
    labels = page.locator(CURRENCY_LABEL_SELECTOR)
    label_count = await labels.count()
    LOGGER.debug("Found %d currency label elements", label_count)
    
    match = labels.filter(has_text=re.compile(rf"^\s*{re.escape(currency)}\s*$", re.I)).first
    match_count = await match.count()
    LOGGER.debug("Currency selector match count for '%s': %d", currency, match_count)
    
    if not match_count:
        raise FetchError(f"Currency selector not found for: {currency}")

    await match.click()
    LOGGER.debug("Currency button clicked for: %s", currency)
    await asyncio.sleep(0.5)  # Allow UI to update
    LOGGER.info("Currency activated: %s", currency)


def _clean(value: str) -> str:
    return " ".join(value.split())
