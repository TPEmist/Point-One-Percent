"""
AegisBrowserInjector: CDP-based browser injector with iframe traversal.

Connects to an already-running Chromium browser (via --remote-debugging-port)
and auto-fills credit card fields on the active page — including fields inside
Stripe and other third-party payment iframes.
"""
from __future__ import annotations

import logging
from typing import Optional

from aegis.core.state import AegisStateTracker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Common CSS selectors for credit card fields across major payment providers
# ---------------------------------------------------------------------------
CARD_NUMBER_SELECTORS = [
    "input[autocomplete='cc-number']",
    "input[name='cardnumber']",
    "input[name='card_number']",
    "input[name='card-number']",
    "input[id*='card'][id*='number']",
    "input[placeholder*='Card number']",
    "input[placeholder*='card number']",
    "input[data-elements-stable-field-name='cardNumber']",   # Stripe Elements
    "input.__PrivateStripeElement",                          # Stripe v2
]

EXPIRY_SELECTORS = [
    "input[autocomplete='cc-exp']",
    "input[name='cc-exp']",
    "input[name='expiry']",
    "input[name='card_expiry']",
    "input[placeholder*='MM / YY']",
    "input[placeholder*='MM/YY']",
    "input[placeholder*='Expiry']",
    "input[data-elements-stable-field-name='cardExpiry']",   # Stripe Elements
]

CVV_SELECTORS = [
    "input[autocomplete='cc-csc']",
    "input[name='cvc']",
    "input[name='cvv']",
    "input[name='security_code']",
    "input[name='card_cvc']",
    "input[placeholder*='CVC']",
    "input[placeholder*='CVV']",
    "input[placeholder*='Security code']",
    "input[data-elements-stable-field-name='cardCvc']",      # Stripe Elements
]


class AegisBrowserInjector:
    """
    Attaches to a running Chromium browser via CDP and injects
    card credentials into whatever page is currently active.

    The browser must be launched with --remote-debugging-port=9222.
    Example:
        chromium --remote-debugging-port=9222 https://checkout.example.com

    Usage:
        injector = AegisBrowserInjector(state_tracker)
        success = await injector.inject_payment_info(seal_id)
    """

    def __init__(self, state_tracker: AegisStateTracker):
        self.state_tracker = state_tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def inject_payment_info(
        self,
        seal_id: str,
        cdp_url: str = "http://localhost:9222",
    ) -> bool:
        """
        Connect to an existing Chromium browser via CDP, find payment fields
        across all frames (including nested third-party iframes), fill them
        with real card details, then disconnect without closing the browser.

        Returns:
            True  — card number field was found and filled successfully.
            False — no card input fields found on the active page/frames.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright is not installed. "
                "Run: pip install aegis-pay[browser]  or  pip install playwright"
            )
            return False

        details = self.state_tracker.get_seal_details(seal_id)
        if not details:
            logger.error("AegisBrowserInjector: seal_id '%s' not found in DB.", seal_id)
            return False

        card_number: str = details.get("card_number", "")
        cvv: str = details.get("cvv", "")
        expiry: str = details.get("expiration_date", "")

        browser = None
        try:
            async with async_playwright() as pw:
                # Connect to the *existing* browser — does NOT launch a new instance
                browser = await pw.chromium.connect_over_cdp(cdp_url)

                contexts = browser.contexts
                if not contexts or not contexts[0].pages:
                    logger.warning(
                        "AegisBrowserInjector: no open pages found via CDP at %s",
                        cdp_url,
                    )
                    return False

                page = contexts[0].pages[0]
                await page.bring_to_front()

                filled = await self._fill_across_frames(page, card_number, expiry, cvv)
                return filled

        except Exception as exc:
            logger.error("AegisBrowserInjector error: %s", exc, exc_info=True)
            return False
        finally:
            # Disconnect the playwright session — does NOT close the real browser
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fill_across_frames(
        self, page, card_number: str, expiry: str, cvv: str
    ) -> bool:
        """
        Walk every frame in the page tree (flat list from Playwright includes
        all nested iframes). Return True as soon as the card number is filled.
        """
        all_frames = page.frames  # includes main frame + all nested iframes
        card_filled = False

        for frame in all_frames:
            try:
                if await self._fill_in_frame(frame, card_number, expiry, cvv):
                    card_filled = True
                    # Keep going for expiry/CVV in case they are in sibling iframes
                    # (common in Stripe's multi-iframe layout)
            except Exception as frame_exc:
                logger.debug("Frame %s skipped: %s", frame.url, frame_exc)
                continue

        return card_filled

    async def _fill_in_frame(
        self, frame, card_number: str, expiry: str, cvv: str
    ) -> bool:
        """
        Attempt to fill card fields inside a single frame.
        Returns True if the card number field was found and filled; False otherwise.
        """
        card_locator = await self._find_visible_locator(frame, CARD_NUMBER_SELECTORS)
        if card_locator is None:
            return False

        await card_locator.fill(card_number)
        logger.info(
            "AegisBrowserInjector: ✅ card number injected in frame '%s'", frame.url
        )

        expiry_locator = await self._find_visible_locator(frame, EXPIRY_SELECTORS)
        if expiry_locator:
            await expiry_locator.fill(expiry)
            logger.info("AegisBrowserInjector: expiry injected.")

        cvv_locator = await self._find_visible_locator(frame, CVV_SELECTORS)
        if cvv_locator:
            await cvv_locator.fill(cvv)
            logger.info("AegisBrowserInjector: CVV injected.")

        return True

    @staticmethod
    async def _find_visible_locator(frame, selectors: list):
        """
        Try each CSS selector in order; return the first match in
        the given frame, or None if nothing is found.
        (We removed is_visible() because cross-origin opacity/display rules
        in Stripe iframes sometimes cause it to falsely return False).
        """
        for selector in selectors:
            try:
                locator = frame.locator(selector).first
                count = await locator.count()
                if count > 0:
                    return locator
            except Exception:
                continue
        return None
