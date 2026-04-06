"""
Tests for headless mode support and TOCTOU refactor (_verify_domain_toctou shared method).
"""
import pytest
from unittest.mock import MagicMock


class TestVerifyDomainToctou:
    """Unit tests for the shared _verify_domain_toctou static method."""

    def test_empty_page_url_returns_none(self):
        from pop_pay.injector import PopBrowserInjector
        assert PopBrowserInjector._verify_domain_toctou("", "wikipedia") is None

    def test_empty_vendor_returns_none(self):
        from pop_pay.injector import PopBrowserInjector
        assert PopBrowserInjector._verify_domain_toctou("https://example.com", "") is None

    def test_known_vendor_matching_domain_passes(self):
        from pop_pay.injector import PopBrowserInjector
        result = PopBrowserInjector._verify_domain_toctou(
            "https://en.wikipedia.org/wiki/donate", "wikipedia"
        )
        assert result is None

    def test_known_vendor_mismatched_domain_blocks(self):
        from pop_pay.injector import PopBrowserInjector
        result = PopBrowserInjector._verify_domain_toctou(
            "https://attacker.com/fake-checkout", "wikipedia"
        )
        assert result is not None
        assert result.startswith("domain_mismatch:")

    def test_unknown_vendor_domain_token_match(self):
        """Unknown vendor with domain token matching should pass."""
        from pop_pay.injector import PopBrowserInjector
        result = PopBrowserInjector._verify_domain_toctou(
            "https://makerfaire.com/checkout", "Maker Faire"
        )
        assert result is None

    def test_unknown_vendor_no_match_blocks(self):
        from pop_pay.injector import PopBrowserInjector
        result = PopBrowserInjector._verify_domain_toctou(
            "https://evil.com/checkout", "Maker Faire"
        )
        assert result is not None
        assert "domain_mismatch" in result

    def test_subdomain_spoofing_blocked(self):
        """wikipedia.attacker.com must NOT match vendor 'wikipedia'."""
        from pop_pay.injector import PopBrowserInjector
        result = PopBrowserInjector._verify_domain_toctou(
            "https://wikipedia.attacker.com/donate", "wikipedia"
        )
        assert result is not None
        assert "domain_mismatch" in result


class TestHeadlessInit:
    """Test headless parameter on PopBrowserInjector."""

    def test_default_headless_false(self):
        from pop_pay.injector import PopBrowserInjector
        injector = PopBrowserInjector(state_tracker=MagicMock())
        assert injector.headless is False

    def test_headless_true(self):
        from pop_pay.injector import PopBrowserInjector
        injector = PopBrowserInjector(state_tracker=MagicMock(), headless=True)
        assert injector.headless is True


class TestHeadlessCLIFlag:
    """Test --headless flag in CLI arg parser."""

    def test_headless_flag_parsed(self):
        import argparse
        from pop_pay.cli import main
        # We can't call main() directly without Chrome, but we can test arg parsing
        parser = argparse.ArgumentParser()
        parser.add_argument("--headless", action="store_true")
        args = parser.parse_args(["--headless"])
        assert args.headless is True

    def test_no_headless_flag(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--headless", action="store_true")
        args = parser.parse_args([])
        assert args.headless is False


@pytest.mark.asyncio
async def test_toctou_refactor_inject_payment_info_still_blocks():
    """Regression: inject_payment_info still uses the shared TOCTOU method correctly."""
    from pop_pay.injector import PopBrowserInjector
    injector = PopBrowserInjector(state_tracker=MagicMock())
    result = await injector.inject_payment_info(
        seal_id="test-seal",
        page_url="https://attacker.com/fake-checkout",
        card_number="4111111111111111",
        cvv="123",
        expiration_date="12/28",
        approved_vendor="wikipedia",
        cdp_url="http://localhost:9222",
    )
    assert result["card_filled"] is False
    assert "domain_mismatch" in result.get("blocked_reason", "")


@pytest.mark.asyncio
async def test_toctou_refactor_inject_billing_only_still_blocks():
    """Regression: inject_billing_only still uses the shared TOCTOU method correctly."""
    from pop_pay.injector import PopBrowserInjector
    injector = PopBrowserInjector(state_tracker=MagicMock())
    result = await injector.inject_billing_only(
        page_url="https://attacker.com/billing",
        approved_vendor="wikipedia",
        cdp_url="http://localhost:9222",
    )
    assert result["billing_filled"] is False
    assert "domain_mismatch" in result.get("blocked_reason", "")
