"""
Tests for biometric/webhook approval hook (POP_APPROVAL_WEBHOOK).
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


@pytest.mark.asyncio
async def test_approval_webhook_auto_approve_when_not_configured():
    """When no approval webhook is configured, _request_human_approval auto-approves."""
    import pop_pay.mcp_server as srv
    original = srv.approval_webhook_url
    try:
        srv.approval_webhook_url = None
        approved, reason = await srv._request_human_approval(
            merchant="AWS", amount=50.0, reasoning="test", seal_id="seal-123"
        )
        assert approved is True
        assert "auto-approved" in reason
    finally:
        srv.approval_webhook_url = original


@pytest.mark.asyncio
async def test_approval_webhook_ssrf_blocks_private_ip():
    """Approval webhook must block private IPs."""
    import pop_pay.mcp_server as srv
    original = srv.approval_webhook_url
    try:
        srv.approval_webhook_url = "http://192.168.1.1/approve"
        approved, reason = await srv._request_human_approval(
            merchant="AWS", amount=50.0, reasoning="test", seal_id="seal-123"
        )
        assert approved is False
        assert "SSRF" in reason
    finally:
        srv.approval_webhook_url = original


@pytest.mark.asyncio
async def test_approval_webhook_ssrf_blocks_loopback():
    """Approval webhook must block loopback addresses."""
    import pop_pay.mcp_server as srv
    original = srv.approval_webhook_url
    try:
        srv.approval_webhook_url = "http://127.0.0.1:8080/approve"
        approved, reason = await srv._request_human_approval(
            merchant="AWS", amount=50.0, reasoning="test", seal_id="seal-123"
        )
        assert approved is False
        assert "SSRF" in reason
    finally:
        srv.approval_webhook_url = original


@pytest.mark.asyncio
async def test_approval_webhook_approved_response():
    """Webhook returning approved=true should approve."""
    import pop_pay.mcp_server as srv
    original = srv.approval_webhook_url
    try:
        srv.approval_webhook_url = "https://approvals.example.com/hook"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"approved": True, "reason": "looks good"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pop_pay.mcp_server.httpx.AsyncClient", return_value=mock_client):
            approved, reason = await srv._request_human_approval(
                merchant="AWS", amount=50.0, reasoning="test", seal_id="seal-123"
            )
        assert approved is True
        assert reason == "looks good"
    finally:
        srv.approval_webhook_url = original


@pytest.mark.asyncio
async def test_approval_webhook_rejected_response():
    """Webhook returning approved=false should reject."""
    import pop_pay.mcp_server as srv
    original = srv.approval_webhook_url
    try:
        srv.approval_webhook_url = "https://approvals.example.com/hook"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"approved": False, "reason": "too expensive"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pop_pay.mcp_server.httpx.AsyncClient", return_value=mock_client):
            approved, reason = await srv._request_human_approval(
                merchant="AWS", amount=50.0, reasoning="test", seal_id="seal-123"
            )
        assert approved is False
        assert reason == "too expensive"
    finally:
        srv.approval_webhook_url = original


@pytest.mark.asyncio
async def test_approval_webhook_network_error_rejects():
    """Webhook network failure should reject the payment (fail-closed)."""
    import pop_pay.mcp_server as srv
    original = srv.approval_webhook_url
    try:
        srv.approval_webhook_url = "https://approvals.example.com/hook"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pop_pay.mcp_server.httpx.AsyncClient", return_value=mock_client):
            approved, reason = await srv._request_human_approval(
                merchant="AWS", amount=50.0, reasoning="test", seal_id="seal-123"
            )
        assert approved is False
        assert "error" in reason.lower()
    finally:
        srv.approval_webhook_url = original
