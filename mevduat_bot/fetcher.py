from __future__ import annotations

import asyncio
import re
from pathlib import Path

from playwright.async_api import BrowserContext, Error, Page, TimeoutError, async_playwright

from .config import Settings
from .models import MevduatSnapshot


CARD_SELECTOR = "#block-bistkydendeksleri"
TABLE_BODY_SELECTOR = "#table-2-9-data"
ROW_SELECTOR = f"{TABLE_BODY_SELECTOR} tr"
CURRENCY_LABEL_SELECTOR = "label.btn.btn-info.smaller-text"


class FetchError(RuntimeError):
    """Raised when the target page cannot be parsed safely."""


async def fetch_snapshot(settings: Settings, screenshot_path: Path) -> MevduatSnapshot:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=settings.playwright_headless)
        try:
            context = await browser.new_context(
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                viewport={"width": 1600, "height": 1400},
            )
            try:
                return await _fetch_with_context(context, settings, screenshot_path)
            finally:
                await context.close()
        finally:
            await browser.close()


async def _fetch_with_context(
    context: BrowserContext,
    settings: Settings,
    screenshot_path: Path,
) -> MevduatSnapshot:
    page = await context.new_page()
    page.set_default_timeout(30_000)

    try:
        await page.goto(settings.target_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        await _dismiss_cookie_banner(page)
        await _activate_currency(page, settings.target_currency)
        row = page.locator(ROW_SELECTOR).first
        await row.wait_for(state="visible")
        await page.wait_for_function(
            """([selector, expectedCurrency]) => {
                const row = document.querySelector(selector);
                if (!row) {
                    return false;
                }
                const cells = row.querySelectorAll("td");
                return cells.length > 7 && cells[7].textContent.trim() === expectedCurrency;
            }""",
            [ROW_SELECTOR, settings.target_currency],
        )

        cells = [text.strip() for text in await row.locator("td").all_inner_texts()]
        if len(cells) < 6 or not cells[3].strip():
            raise FetchError("Table row is missing expected columns or current value.")

        card = page.locator(CARD_SELECTOR)
        await card.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        await card.screenshot(path=str(screenshot_path))

        return MevduatSnapshot(
            index_name=_clean(cells[0]),
            index_code=_clean(cells[1]),
            updated_at=_clean(cells[2]),
            current_value=_clean(cells[3]),
            daily_change_percent=_clean(cells[4]),
            currency=settings.target_currency,
        )
    except TimeoutError as exc:
        raise FetchError("Timed out while waiting for the mevduat table to load.") from exc
    except Error as exc:
        raise FetchError(f"Playwright failed to load the target page: {exc}") from exc
    finally:
        await page.close()


async def _dismiss_cookie_banner(page: Page) -> None:
    button = page.locator("button").filter(
        has_text=re.compile(r"t[üu]m[üu]n[üu]\s+kabul\s+et", re.I)
    ).first
    if await button.count():
        try:
            await button.click(timeout=5_000)
        except TimeoutError:
            return


async def _activate_currency(page: Page, currency: str) -> None:
    labels = page.locator(CURRENCY_LABEL_SELECTOR)
    match = labels.filter(has_text=currency).first
    await match.click()
    await page.wait_for_function(
        """([selector, value]) => {
            const label = document.querySelector(selector);
            return Boolean(label && label.textContent && label.textContent.trim() === value);
        }""",
        [".btn-group-toggle .active-input", currency],
    )


def _clean(value: str) -> str:
    return " ".join(value.split())
