"""
Tests for x402 protocol support in MCP server.
"""
import os
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_x402_missing_wallet_key_rejected():
    """x402 payment must be rejected when POP_X402_WALLET_KEY is not set."""
    from pop_pay.mcp_server import request_x402_payment

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("POP_X402_WALLET_KEY", None)
        result = await request_x402_payment(
            amount=10.0,
            service_url="https://api.example.com/resource",
            reasoning="Test payment",
        )
    assert "POP_X402_WALLET_KEY" in result
    assert "rejected" in result.lower()


@pytest.mark.asyncio
async def test_x402_ssrf_private_ip_blocked():
    """x402 must block service_url pointing to a private IP."""
    from pop_pay.mcp_server import request_x402_payment

    with patch.dict(os.environ, {"POP_X402_WALLET_KEY": "test-key-123"}):
        result = await request_x402_payment(
            amount=5.0,
            service_url="http://192.168.1.1/api/pay",
            reasoning="SSRF test",
        )
    assert "SSRF" in result or "private" in result.lower()


@pytest.mark.asyncio
async def test_x402_ssrf_loopback_blocked():
    """x402 must block service_url pointing to loopback."""
    from pop_pay.mcp_server import request_x402_payment

    with patch.dict(os.environ, {"POP_X402_WALLET_KEY": "test-key-123"}):
        result = await request_x402_payment(
            amount=5.0,
            service_url="http://127.0.0.1:8080/api/pay",
            reasoning="Loopback test",
        )
    assert "SSRF" in result or "private" in result.lower()


@pytest.mark.asyncio
async def test_x402_guardrail_integration():
    """x402 payment must go through guardrail evaluation (amount check)."""
    from pop_pay.mcp_server import request_x402_payment

    # Set wallet key but use an amount that exceeds the per-tx limit
    with patch.dict(os.environ, {"POP_X402_WALLET_KEY": "test-key-123"}):
        # The default POP_MAX_PER_TX is 100.0, so 9999 should be rejected
        result = await request_x402_payment(
            amount=9999.0,
            service_url="https://api.example.com/expensive",
            reasoning="Expensive resource",
        )
    assert "rejected" in result.lower()


@pytest.mark.asyncio
async def test_x402_valid_request_returns_stubbed():
    """x402 payment with valid params should return stubbed approval."""
    from pop_pay.mcp_server import request_x402_payment

    # The x402 tool uses service_url as target_vendor for guardrails.
    # Use a URL whose domain matches an allowed category ("cloudflare").
    with patch.dict(os.environ, {
        "POP_X402_WALLET_KEY": "test-key-123",
        "POP_ALLOWED_CATEGORIES": '["aws", "cloudflare", "api.cloudflare.com"]',
    }):
        # Reload allowed categories in the mcp_server module
        import pop_pay.mcp_server as srv
        import json
        original_cats = srv.allowed_categories
        srv.allowed_categories = json.loads(os.environ["POP_ALLOWED_CATEGORIES"])
        srv.policy.allowed_categories = srv.allowed_categories
        try:
            result = await request_x402_payment(
                amount=5.0,
                service_url="https://api.cloudflare.com/resource",
                reasoning="Need cloudflare resource",
            )
        finally:
            srv.allowed_categories = original_cats
            srv.policy.allowed_categories = original_cats
    assert "stubbed" in result.lower() or "STUBBED" in result


def test_ssrf_validate_url_helper():
    """Test the _ssrf_validate_url helper directly."""
    from pop_pay.mcp_server import _ssrf_validate_url

    assert _ssrf_validate_url("https://example.com/api") is None
    assert _ssrf_validate_url("http://example.com/api") is None
    assert _ssrf_validate_url("ftp://example.com/file") is not None
    assert _ssrf_validate_url("http://127.0.0.1/api") is not None
    assert _ssrf_validate_url("http://192.168.1.1/api") is not None
    assert _ssrf_validate_url("http://10.0.0.1/api") is not None
