"""v0.8.2 — Handler-level tests for request_purchaser_info.

Drives the MCP tool through each exit point and asserts the audit_log row
written is correct (outcome + rejection_reason). Also covers the
POP_PURCHASER_INFO_BLOCKING toggle.
"""
import os
import tempfile

import pytest


class _FakeInjectorOK:
    """Minimal injector stub — always fills billing successfully."""
    async def inject_billing_only(self, cdp_url=None, page_url=None, approved_vendor=None):
        return {"blocked_reason": "", "billing_filled": True}


class _FakeInjectorDomainMismatch:
    async def inject_billing_only(self, cdp_url=None, page_url=None, approved_vendor=None):
        return {"blocked_reason": "domain_mismatch:evil.example.com", "billing_filled": False}


class _FakeInjectorNoFields:
    async def inject_billing_only(self, cdp_url=None, page_url=None, approved_vendor=None):
        return {"blocked_reason": "", "billing_filled": False}


@pytest.fixture
def handler_env(monkeypatch):
    """Swap the module-level client.state_tracker to a temp DB and give a
    hook to replace the injector + env var per test. Yields a helper dict.

    IMPORTANT: PopStateTracker does NOT accept :memory: safely because the
    handler may open multiple operations; we use a real temp file.
    """
    from pop_pay import mcp_server
    from pop_pay.core.state import PopStateTracker

    tmpdir = tempfile.mkdtemp(prefix="pop-pay-handler-")
    db_path = os.path.join(tmpdir, "pop_state.db")
    tracker = PopStateTracker(db_path)

    # Save + swap module-level references
    original_tracker = mcp_server.client.state_tracker
    original_injector = mcp_server.injector
    original_allowed = list(mcp_server.allowed_categories)
    mcp_server.client.state_tracker = tracker

    yield {
        "module": mcp_server,
        "tracker": tracker,
        "db_path": db_path,
        "set_injector": lambda inj: setattr(mcp_server, "injector", inj),
        "set_allowed_categories": lambda cats: setattr(mcp_server, "allowed_categories", cats),
    }

    # Restore
    mcp_server.client.state_tracker = original_tracker
    mcp_server.injector = original_injector
    mcp_server.allowed_categories = original_allowed
    tracker.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_error_injector_outcome_written(handler_env, monkeypatch):
    """When injector is None, audit row outcome = error_injector."""
    from pop_pay.mcp_server import request_purchaser_info
    handler_env["set_injector"](None)
    monkeypatch.setenv("POP_PURCHASER_INFO_BLOCKING", "true")

    result = await request_purchaser_info(
        target_vendor="aws",
        page_url="",
        reasoning="test",
    )
    assert "not available" in result.lower() or "inject" in result.lower()

    events = handler_env["tracker"].get_audit_events()
    assert len(events) == 1
    assert events[0]["outcome"] == "error_injector"
    assert events[0]["rejection_reason"] is not None
    assert "injector" in events[0]["rejection_reason"].lower()
    assert events[0]["vendor"] == "aws"


@pytest.mark.asyncio
async def test_rejected_vendor_outcome_written_when_blocking_default(handler_env, monkeypatch):
    """Default (blocking=true) — unapproved vendor → outcome=rejected_vendor."""
    from pop_pay.mcp_server import request_purchaser_info
    handler_env["set_injector"](_FakeInjectorOK())
    handler_env["set_allowed_categories"](["aws"])
    monkeypatch.delenv("POP_PURCHASER_INFO_BLOCKING", raising=False)  # default = true

    result = await request_purchaser_info(
        target_vendor="shady-vendor",
        page_url="",
        reasoning="test reason",
    )
    assert "not in your allowed categories" in result.lower()

    events = handler_env["tracker"].get_audit_events()
    assert len(events) == 1
    assert events[0]["outcome"] == "rejected_vendor"
    assert events[0]["rejection_reason"] is not None
    assert "shady-vendor" in events[0]["rejection_reason"]
    assert "POP_ALLOWED_CATEGORIES" in events[0]["rejection_reason"]


@pytest.mark.asyncio
async def test_blocked_bypassed_falls_through_to_injector(handler_env, monkeypatch):
    """When POP_PURCHASER_INFO_BLOCKING=false, unapproved vendor is logged
    as blocked_bypassed and the flow continues to the injector."""
    from pop_pay.mcp_server import request_purchaser_info
    handler_env["set_injector"](_FakeInjectorOK())
    handler_env["set_allowed_categories"](["aws"])
    monkeypatch.setenv("POP_PURCHASER_INFO_BLOCKING", "false")

    result = await request_purchaser_info(
        target_vendor="shady-vendor",
        page_url="",
        reasoning="bypass test",
    )
    # Success message means we reached the injector's approved branch
    assert "filled successfully" in result.lower()

    events = handler_env["tracker"].get_audit_events()
    # Expect two rows: blocked_bypassed then approved. get_audit_events returns
    # most-recent-first.
    assert len(events) == 2
    outcomes_by_id = [e["outcome"] for e in events]
    assert "approved" in outcomes_by_id
    assert "blocked_bypassed" in outcomes_by_id
    bypass_row = next(e for e in events if e["outcome"] == "blocked_bypassed")
    assert "POP_PURCHASER_INFO_BLOCKING=false" in bypass_row["rejection_reason"]


@pytest.mark.asyncio
async def test_approved_outcome_written(handler_env, monkeypatch):
    """Allowed vendor + working injector → outcome=approved, no rejection_reason."""
    from pop_pay.mcp_server import request_purchaser_info
    handler_env["set_injector"](_FakeInjectorOK())
    handler_env["set_allowed_categories"](["aws"])
    monkeypatch.delenv("POP_PURCHASER_INFO_BLOCKING", raising=False)

    result = await request_purchaser_info(
        target_vendor="aws",
        page_url="",
        reasoning="compute",
    )
    assert "filled successfully" in result.lower()

    events = handler_env["tracker"].get_audit_events()
    assert len(events) == 1
    assert events[0]["outcome"] == "approved"
    assert events[0]["rejection_reason"] is None
    assert events[0]["vendor"] == "aws"
    assert events[0]["reasoning"] == "compute"


@pytest.mark.asyncio
async def test_domain_mismatch_outcome_written(handler_env, monkeypatch):
    """Injector returns domain_mismatch → outcome=rejected_security."""
    from pop_pay.mcp_server import request_purchaser_info
    handler_env["set_injector"](_FakeInjectorDomainMismatch())
    handler_env["set_allowed_categories"](["aws"])
    monkeypatch.delenv("POP_PURCHASER_INFO_BLOCKING", raising=False)

    result = await request_purchaser_info(
        target_vendor="aws",
        page_url="",
        reasoning="test",
    )
    assert "does not match" in result.lower() or "domain" in result.lower()

    events = handler_env["tracker"].get_audit_events()
    assert len(events) == 1
    assert events[0]["outcome"] == "rejected_security"
    assert "domain_mismatch" in events[0]["rejection_reason"]


@pytest.mark.asyncio
async def test_error_fields_outcome_written(handler_env, monkeypatch):
    """Injector fails to find billing fields → outcome=error_fields."""
    from pop_pay.mcp_server import request_purchaser_info
    handler_env["set_injector"](_FakeInjectorNoFields())
    handler_env["set_allowed_categories"](["aws"])
    monkeypatch.delenv("POP_PURCHASER_INFO_BLOCKING", raising=False)

    result = await request_purchaser_info(
        target_vendor="aws",
        page_url="",
        reasoning="test",
    )
    assert "billing" in result.lower() and ("not" in result.lower() or "could not" in result.lower())

    events = handler_env["tracker"].get_audit_events()
    assert len(events) == 1
    assert events[0]["outcome"] == "error_fields"
    assert events[0]["rejection_reason"] is not None
