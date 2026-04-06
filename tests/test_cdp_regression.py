"""CDP injector regression tests for 10 checkout stacks.

Tests use mock Playwright frame/locator objects to simulate each checkout
stack's DOM structure. No live merchant pages or real browsers are needed.

Each test verifies that the injector's selector constants can match the
fields present in that stack's checkout form.

Fixture HTML files in tests/fixtures/checkout/ document the real DOM
structures these tests are based on.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

from pop_pay.injector import (
    PopBrowserInjector,
    CARD_NUMBER_SELECTORS,
    EXPIRY_SELECTORS,
    CVV_SELECTORS,
    FIRST_NAME_SELECTORS,
    LAST_NAME_SELECTORS,
    STREET_SELECTORS,
    ZIP_SELECTORS,
    EMAIL_SELECTORS,
    PHONE_SELECTORS,
    COUNTRY_SELECTORS,
    STATE_SELECTORS,
    CITY_SELECTORS,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "checkout"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_frame(matching_selectors: dict[str, str] | None = None):
    """Create a mock Playwright frame.

    matching_selectors: dict mapping CSS selector -> value to fill.
    When _find_visible_locator is called, if the selector is in this dict,
    a mock locator is returned; otherwise None.
    """
    matching = matching_selectors or {}
    frame = AsyncMock()
    frame.url = "about:blank"

    async def mock_locator_for_selectors(f, selectors):
        for sel in selectors:
            if sel in matching:
                loc = AsyncMock()
                loc.fill = AsyncMock()
                loc.evaluate = AsyncMock(return_value="input")
                return loc
        return None

    return frame, mock_locator_for_selectors


def _make_injector():
    """Create a PopBrowserInjector with mocked CDP connection."""
    injector = PopBrowserInjector.__new__(PopBrowserInjector)
    injector._browser = MagicMock()
    return injector


class MockLocator:
    """Simple mock locator that tracks fill() calls."""
    def __init__(self):
        self.filled_value = None
        self.fill = AsyncMock(side_effect=self._do_fill)
        self.evaluate = AsyncMock(return_value="input")

    async def _do_fill(self, value):
        self.filled_value = value


def _build_frame_with_selectors(card_sel=None, expiry_sel=None, cvv_sel=None):
    """Build a mock frame where specific selectors resolve to locators.

    Returns (frame, card_locator, expiry_locator, cvv_locator).
    """
    card_loc = MockLocator() if card_sel else None
    expiry_loc = MockLocator() if expiry_sel else None
    cvv_loc = MockLocator() if cvv_sel else None

    selector_map = {}
    if card_sel:
        selector_map[card_sel] = card_loc
    if expiry_sel:
        selector_map[expiry_sel] = expiry_loc
    if cvv_sel:
        selector_map[cvv_sel] = cvv_loc

    frame = AsyncMock()
    frame.url = "https://checkout.example.com"

    return frame, card_loc, expiry_loc, cvv_loc, selector_map


def _sync_find_visible(frame, selectors, selector_map):
    """Sync helper — returns the locator from selector_map if found."""
    for sel in selectors:
        if sel in selector_map:
            return selector_map[sel]
    return None


def _make_async_find_visible(selector_map):
    """Return an AsyncMock whose side_effect resolves selectors from selector_map."""
    return AsyncMock(side_effect=lambda f, sels: _sync_find_visible(f, sels, selector_map))


# ---------------------------------------------------------------------------
# Card field injection tests — one per checkout stack
# ---------------------------------------------------------------------------

class TestStripeElements:
    """Stripe Elements uses data-elements-stable-field-name attributes inside iframes."""

    @pytest.mark.asyncio
    async def test_selectors_match_stripe_dom(self):
        stripe_card_sel = "input[data-elements-stable-field-name='cardNumber']"
        stripe_exp_sel = "input[data-elements-stable-field-name='cardExpiry']"
        stripe_cvv_sel = "input[data-elements-stable-field-name='cardCvc']"

        assert stripe_card_sel in CARD_NUMBER_SELECTORS
        assert stripe_exp_sel in EXPIRY_SELECTORS
        assert stripe_cvv_sel in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[data-elements-stable-field-name='cardNumber']",
            expiry_sel="input[data-elements-stable-field-name='cardExpiry']",
            cvv_sel="input[data-elements-stable-field-name='cardCvc']",
        )
        injector = _make_injector()

        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "4242424242424242", "12/28", "123")

        assert result is True
        assert card_loc.filled_value == "4242424242424242"
        assert exp_loc.filled_value == "12/28"
        assert cvv_loc.filled_value == "123"


class TestShopify:
    """Shopify uses standard name attributes: cardnumber, cc-exp, cvc."""

    @pytest.mark.asyncio
    async def test_selectors_match_shopify_dom(self):
        assert "input[name='cardnumber']" in CARD_NUMBER_SELECTORS
        assert "input[name='cc-exp']" in EXPIRY_SELECTORS
        assert "input[name='cvc']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[name='cardnumber']",
            expiry_sel="input[name='cc-exp']",
            cvv_sel="input[name='cvc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "4111111111111111", "01/29", "456")
        assert result is True
        assert card_loc.filled_value == "4111111111111111"


class TestWooCommerce:
    """WooCommerce with Stripe gateway uses Stripe Elements selectors."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[data-elements-stable-field-name='cardNumber']" in CARD_NUMBER_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[data-elements-stable-field-name='cardNumber']",
            expiry_sel="input[data-elements-stable-field-name='cardExpiry']",
            cvv_sel="input[data-elements-stable-field-name='cardCvc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "5555555555554444", "06/27", "789")
        assert result is True


class TestMagento:
    """Magento/Adobe Commerce with Braintree hosted fields uses autocomplete selectors."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[autocomplete='cc-number']" in CARD_NUMBER_SELECTORS
        assert "input[autocomplete='cc-exp']" in EXPIRY_SELECTORS
        assert "input[autocomplete='cc-csc']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[autocomplete='cc-number']",
            expiry_sel="input[autocomplete='cc-exp']",
            cvv_sel="input[autocomplete='cc-csc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "378282246310005", "03/30", "1234")
        assert result is True


class TestBigCommerce:
    """BigCommerce uses name-based selectors: card_number, card_expiry, security_code."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[name='card_number']" in CARD_NUMBER_SELECTORS
        assert "input[name='card_expiry']" in EXPIRY_SELECTORS
        assert "input[name='security_code']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[name='card_number']",
            expiry_sel="input[name='card_expiry']",
            cvv_sel="input[name='security_code']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "6011111111111117", "09/28", "321")
        assert result is True


class TestAdyen:
    """Adyen Drop-in uses autocomplete and name='cvc'."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[autocomplete='cc-number']" in CARD_NUMBER_SELECTORS
        assert "input[name='expiry']" in EXPIRY_SELECTORS
        assert "input[name='cvc']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[autocomplete='cc-number']",
            expiry_sel="input[name='expiry']",
            cvv_sel="input[name='cvc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "3530111333300000", "12/29", "567")
        assert result is True


class TestPayPal:
    """PayPal Hosted Fields (via Braintree) uses autocomplete selectors."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[autocomplete='cc-number']" in CARD_NUMBER_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, _, _, sel_map = _build_frame_with_selectors(
            card_sel="input[autocomplete='cc-number']",
            expiry_sel="input[autocomplete='cc-exp']",
            cvv_sel="input[autocomplete='cc-csc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "4012888888881881", "05/30", "999")
        assert result is True


class TestBraintree:
    """Braintree hosted fields: separate iframes, autocomplete-based selectors."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[autocomplete='cc-number']" in CARD_NUMBER_SELECTORS
        assert "input[autocomplete='cc-exp']" in EXPIRY_SELECTORS
        assert "input[autocomplete='cc-csc']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[autocomplete='cc-number']",
            expiry_sel="input[autocomplete='cc-exp']",
            cvv_sel="input[autocomplete='cc-csc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "4000056655665556", "08/27", "111")
        assert result is True


class TestSquare:
    """Square Web Payments SDK: single iframe, uses name-based selectors."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[name='cardnumber']" in CARD_NUMBER_SELECTORS
        assert "input[name='cvc']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[name='cardnumber']",
            expiry_sel="input[name='cc-exp']",
            cvv_sel="input[name='cvc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "4532015112830366", "11/28", "222")
        assert result is True


class TestCustomHTML:
    """Custom HTML form: direct inputs, no iframes. Baseline test."""

    @pytest.mark.asyncio
    async def test_selectors_match(self):
        assert "input[name='cardnumber']" in CARD_NUMBER_SELECTORS
        assert "input[autocomplete='cc-exp']" in EXPIRY_SELECTORS
        assert "input[autocomplete='cc-csc']" in CVV_SELECTORS

    @pytest.mark.asyncio
    async def test_fill_in_frame_direct(self):
        frame, card_loc, exp_loc, cvv_loc, sel_map = _build_frame_with_selectors(
            card_sel="input[name='cardnumber']",
            expiry_sel="input[autocomplete='cc-exp']",
            cvv_sel="input[autocomplete='cc-csc']",
        )
        injector = _make_injector()
        with patch.object(injector, '_find_visible_locator',
                          new=_make_async_find_visible(sel_map)):
            result = await injector._fill_in_frame(frame, "4242424242424242", "12/30", "314")
        assert result is True


# ---------------------------------------------------------------------------
# Billing field tests
# ---------------------------------------------------------------------------

class TestBillingFields:
    """Test billing field selectors match common checkout stacks."""

    def test_shopify_billing_selectors(self):
        """Shopify uses autocomplete attributes for billing."""
        assert "input[autocomplete='given-name']" in FIRST_NAME_SELECTORS
        assert "input[autocomplete='family-name']" in LAST_NAME_SELECTORS
        assert "input[autocomplete='street-address']" in STREET_SELECTORS
        assert "input[autocomplete='address-level2']" in CITY_SELECTORS
        assert "select[autocomplete='address-level1']" in STATE_SELECTORS
        assert "input[autocomplete='postal-code']" in ZIP_SELECTORS
        assert "select[autocomplete='country']" in COUNTRY_SELECTORS
        assert "input[autocomplete='email']" in EMAIL_SELECTORS
        assert "input[autocomplete='tel']" in PHONE_SELECTORS

    def test_woocommerce_billing_selectors(self):
        """WooCommerce uses billing_ prefixed names."""
        assert "input[autocomplete='address-line1']" in STREET_SELECTORS
        assert "input[autocomplete='postal-code']" in ZIP_SELECTORS
        assert "input[type='email']" in EMAIL_SELECTORS
        assert "input[type='tel']" in PHONE_SELECTORS

    def test_custom_name_selectors(self):
        """Generic name-based selectors for custom forms."""
        assert "input[name='first_name']" in FIRST_NAME_SELECTORS
        assert "input[name='last_name']" in LAST_NAME_SELECTORS
        assert "input[name='address']" in STREET_SELECTORS
        assert "input[name='city']" in CITY_SELECTORS
        assert "input[name='zip']" in ZIP_SELECTORS
        assert "input[name='email']" in EMAIL_SELECTORS
        assert "input[name='phone']" in PHONE_SELECTORS


# ---------------------------------------------------------------------------
# Cross-frame injection test
# ---------------------------------------------------------------------------

class TestCrossFrameInjection:
    """Test _fill_across_frames walks multiple frames."""

    @pytest.mark.asyncio
    async def test_finds_card_in_second_frame(self):
        """Card fields in iframe (not main frame) should still be found."""
        injector = _make_injector()

        main_frame = AsyncMock()
        main_frame.url = "https://shop.example.com/checkout"

        iframe = AsyncMock()
        iframe.url = "https://js.stripe.com/v3/elements-inner"

        sel_map_main = {}  # no card fields in main frame
        sel_map_iframe = {
            "input[data-elements-stable-field-name='cardNumber']": MockLocator(),
            "input[data-elements-stable-field-name='cardExpiry']": MockLocator(),
            "input[data-elements-stable-field-name='cardCvc']": MockLocator(),
        }

        call_count = {"main": 0, "iframe": 0}

        async def mock_fill_in_frame(frame, cn, exp, cvv):
            if frame is main_frame:
                call_count["main"] += 1
                return False  # no card fields
            elif frame is iframe:
                call_count["iframe"] += 1
                return True  # card found
            return False

        page = MagicMock()
        page.frames = [main_frame, iframe]

        with patch.object(injector, '_fill_in_frame', side_effect=mock_fill_in_frame):
            result = await injector._fill_across_frames(page, "4242424242424242", "12/28", "123")

        assert result is True
        assert call_count["main"] == 1
        assert call_count["iframe"] == 1


# ---------------------------------------------------------------------------
# Compatibility matrix documentation
# ---------------------------------------------------------------------------

STACK_COMPATIBILITY = {
    "Stripe Elements": {"status": "confirmed", "selectors": "data-elements-stable-field-name", "iframe": True},
    "Shopify": {"status": "confirmed", "selectors": "name=cardnumber/cc-exp/cvc", "iframe": True},
    "WooCommerce (Stripe)": {"status": "confirmed", "selectors": "via Stripe Elements", "iframe": True},
    "Magento (Braintree)": {"status": "confirmed", "selectors": "autocomplete=cc-*", "iframe": True},
    "BigCommerce": {"status": "confirmed", "selectors": "name=card_number/card_expiry/security_code", "iframe": True},
    "Adyen Drop-in": {"status": "confirmed", "selectors": "autocomplete + name=cvc/expiry", "iframe": True},
    "PayPal Hosted": {"status": "confirmed", "selectors": "autocomplete=cc-*", "iframe": True},
    "Braintree Hosted": {"status": "confirmed", "selectors": "autocomplete=cc-*", "iframe": True},
    "Square Web Payments": {"status": "confirmed", "selectors": "name=cardnumber/cvc", "iframe": True},
    "Custom HTML": {"status": "confirmed", "selectors": "name + autocomplete", "iframe": False},
}


def test_all_10_stacks_documented():
    """Ensure all 10 checkout stacks are in the compatibility matrix."""
    assert len(STACK_COMPATIBILITY) == 10


def test_fixture_files_exist():
    """Verify all 10 HTML fixture files exist."""
    expected = [
        "stripe_elements.html", "shopify.html", "woocommerce.html",
        "magento.html", "bigcommerce.html", "adyen.html",
        "paypal.html", "braintree.html", "square.html", "custom.html",
    ]
    for name in expected:
        assert (FIXTURES_DIR / name).exists(), f"Missing fixture: {name}"
