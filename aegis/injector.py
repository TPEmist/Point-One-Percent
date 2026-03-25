"""
AegisBrowserInjector: CDP-based browser injector with iframe traversal.

Connects to an already-running Chromium browser (via --remote-debugging-port)
and auto-fills credit card fields on the active page — including fields inside
Stripe and other third-party payment iframes.  Also fills billing detail fields
(name, address, email) that live in the main page frame.
"""
from __future__ import annotations

import logging
import os
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

# ---------------------------------------------------------------------------
# Common CSS selectors for billing detail fields (main page frame, not iframes)
# ---------------------------------------------------------------------------
FIRST_NAME_SELECTORS = [
    "input[autocomplete='given-name']",
    "input[name='first_name']",
    "input[name='firstName']",
    "input[name='first-name']",
    "input[id*='first'][id*='name']",
    "input[id='first_name']",
    "input[id='firstName']",
    "input[placeholder*='First name']",
    "input[placeholder*='first name']",
    "input[aria-label*='First name']",
    "input[aria-label*='first name']",
]

LAST_NAME_SELECTORS = [
    "input[autocomplete='family-name']",
    "input[name='last_name']",
    "input[name='lastName']",
    "input[name='last-name']",
    "input[id*='last'][id*='name']",
    "input[id='last_name']",
    "input[id='lastName']",
    "input[placeholder*='Last name']",
    "input[placeholder*='last name']",
    "input[aria-label*='Last name']",
    "input[aria-label*='last name']",
]

FULL_NAME_SELECTORS = [
    "input[autocomplete='name']",
    "input[name='full_name']",
    "input[name='fullName']",
    "input[name='name']",
    "input[id='full_name']",
    "input[id='fullName']",
    "input[placeholder*='Full name']",
    "input[placeholder*='full name']",
    "input[aria-label*='Full name']",
    "input[aria-label*='full name']",
]

STREET_SELECTORS = [
    "input[autocomplete='street-address']",
    "input[autocomplete='address-line1']",
    "input[name='address']",
    "input[name='address1']",
    "input[name='street']",
    "input[name='street_address']",
    "input[name='billing_address']",
    "input[id*='address']",
    "input[id*='street']",
    "input[placeholder*='Street']",
    "input[placeholder*='street']",
    "input[placeholder*='Address']",
    "input[placeholder*='address']",
    "input[aria-label*='Street']",
    "input[aria-label*='street']",
]

ZIP_SELECTORS = [
    "input[autocomplete='postal-code']",
    "input[name='zip']",
    "input[name='postal_code']",
    "input[name='postcode']",
    "input[name='zipcode']",
    "input[name='zip_code']",
    "input[id*='zip']",
    "input[id*='postal']",
    "input[placeholder*='Zip']",
    "input[placeholder*='zip']",
    "input[placeholder*='Postal']",
    "input[placeholder*='postal']",
    "input[aria-label*='Zip']",
    "input[aria-label*='zip']",
    "input[aria-label*='Postal']",
]

EMAIL_SELECTORS = [
    "input[autocomplete='email']",
    "input[type='email']",
    "input[name='email']",
    "input[name='email_address']",
    "input[id='email']",
    "input[id*='email']",
    "input[placeholder*='Email']",
    "input[placeholder*='email']",
    "input[aria-label*='Email']",
    "input[aria-label*='email']",
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
    ) -> dict:
        """
        Connect to an existing Chromium browser via CDP, find payment fields
        across all frames (including nested third-party iframes), fill them
        with real card details, then disconnect without closing the browser.
        Also fills billing detail fields (name, address, email) from env vars
        in the main page frame, if the env vars are set.

        Returns a dict with:
            "card_filled"    — bool: card number field was found and filled.
            "billing_filled" — bool: at least one billing field was filled.
        For backwards compatibility, the dict is also truthy/falsy based on
        card_filled (via __bool__ semantics of the first value).
        """
        result = {"card_filled": False, "billing_filled": False}

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright is not installed. "
                "Run: pip install aegis-pay[browser]  or  pip install playwright"
            )
            return result

        details = self.state_tracker.get_seal_details(seal_id)
        if not details:
            logger.error("AegisBrowserInjector: seal_id '%s' not found in DB.", seal_id)
            return result

        card_number: str = details.get("card_number", "")
        cvv: str = details.get("cvv", "")
        expiry: str = details.get("expiration_date", "")

        # Collect billing info from env vars — all optional, skip if empty
        billing_info = {
            "first_name": os.getenv("AEGIS_BILLING_FIRST_NAME", "").strip(),
            "last_name":  os.getenv("AEGIS_BILLING_LAST_NAME", "").strip(),
            "street":     os.getenv("AEGIS_BILLING_STREET", "").strip(),
            "zip":        os.getenv("AEGIS_BILLING_ZIP", "").strip(),
            "email":      os.getenv("AEGIS_BILLING_EMAIL", "").strip(),
        }
        has_billing = any(billing_info.values())

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
                    return result

                page = contexts[0].pages[0]
                await page.bring_to_front()

                result["card_filled"] = await self._fill_across_frames(
                    page, card_number, expiry, cvv
                )

                if has_billing:
                    result["billing_filled"] = await self._fill_billing_fields(
                        page, billing_info
                    )

                return result

        except Exception as exc:
            logger.error("AegisBrowserInjector error: %s", exc, exc_info=True)
            return result
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

    async def _fill_billing_fields(self, page, billing_info: dict) -> bool:
        """
        Fill billing detail fields (name, address, email) in the main page frame.
        These fields are standard DOM inputs — NOT inside Stripe iframes.

        Each field is attempted independently; missing selectors are silently skipped.
        Returns True if at least one billing field was successfully filled.
        """
        main_frame = page.main_frame
        any_filled = False

        first_name = billing_info.get("first_name", "")
        last_name  = billing_info.get("last_name", "")
        street     = billing_info.get("street", "")
        zip_code   = billing_info.get("zip", "")
        email      = billing_info.get("email", "")

        # First name
        if first_name:
            locator = await self._find_visible_locator(main_frame, FIRST_NAME_SELECTORS)
            if locator:
                try:
                    await locator.fill(first_name)
                    logger.info("AegisBrowserInjector: first name injected.")
                    any_filled = True
                except Exception as exc:
                    logger.debug("AegisBrowserInjector: could not fill first name: %s", exc)

        # Last name
        if last_name:
            locator = await self._find_visible_locator(main_frame, LAST_NAME_SELECTORS)
            if locator:
                try:
                    await locator.fill(last_name)
                    logger.info("AegisBrowserInjector: last name injected.")
                    any_filled = True
                except Exception as exc:
                    logger.debug("AegisBrowserInjector: could not fill last name: %s", exc)

        # Full name fallback — only used when first+last name fields are absent
        # but a combined "name" field exists on the page
        if first_name or last_name:
            full_name = " ".join(filter(None, [first_name, last_name])).strip()
            if full_name:
                locator = await self._find_visible_locator(main_frame, FULL_NAME_SELECTORS)
                if locator:
                    try:
                        await locator.fill(full_name)
                        logger.info("AegisBrowserInjector: full name injected.")
                        any_filled = True
                    except Exception as exc:
                        logger.debug(
                            "AegisBrowserInjector: could not fill full name: %s", exc
                        )

        # Street address
        if street:
            locator = await self._find_visible_locator(main_frame, STREET_SELECTORS)
            if locator:
                try:
                    await locator.fill(street)
                    logger.info("AegisBrowserInjector: street address injected.")
                    any_filled = True
                except Exception as exc:
                    logger.debug(
                        "AegisBrowserInjector: could not fill street address: %s", exc
                    )

        # Zip / postal code
        if zip_code:
            locator = await self._find_visible_locator(main_frame, ZIP_SELECTORS)
            if locator:
                try:
                    await locator.fill(zip_code)
                    logger.info("AegisBrowserInjector: zip code injected.")
                    any_filled = True
                except Exception as exc:
                    logger.debug("AegisBrowserInjector: could not fill zip code: %s", exc)

        # Email
        if email:
            locator = await self._find_visible_locator(main_frame, EMAIL_SELECTORS)
            if locator:
                try:
                    await locator.fill(email)
                    logger.info("AegisBrowserInjector: email injected.")
                    any_filled = True
                except Exception as exc:
                    logger.debug("AegisBrowserInjector: could not fill email: %s", exc)

        return any_filled

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
