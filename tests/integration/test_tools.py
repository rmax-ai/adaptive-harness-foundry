"""Integration tests for fixture-backed tool implementations."""

from harness_foundry.tools import (
    calculate_refund_eligibility,
    escalate_incident,
    get_customer,
    get_incident_playbook,
    get_transactions,
    search_policy,
)


async def test_get_customer_valid_id_returns_customer() -> None:
    result = await get_customer("C-101")

    assert result["tier"] == "enterprise"
    assert result["status"] == "active"


async def test_get_customer_invalid_id_returns_not_found() -> None:
    result = await get_customer("C-999")

    assert result == {"found": False, "customer_id": "C-999"}


async def test_get_transactions_returns_customer_transactions() -> None:
    result = await get_transactions("C-209")

    assert result["customer_id"] == "C-209"
    assert len(result["transactions"]) == 2
    assert result["transactions"][0]["type"] == "subscription"


async def test_search_policy_refund_returns_relevant_policies() -> None:
    result = await search_policy("refund")

    assert result["policies"]
    assert any(policy["section"] == "POL-REFUND-01" for policy in result["policies"])


async def test_calculate_refund_eligibility_enterprise_within_limit() -> None:
    result = await calculate_refund_eligibility(25, "enterprise")

    assert result["eligible"] is True
    assert result["days_limit"] == 30


async def test_calculate_refund_eligibility_basic_outside_limit() -> None:
    result = await calculate_refund_eligibility(10, "basic")

    assert result["eligible"] is False
    assert result["days_limit"] == 7


async def test_get_incident_playbook_returns_steps() -> None:
    result = await get_incident_playbook("duplicate_charge")

    assert result["issue_type"] == "duplicate_charge"
    assert result["steps"]
    assert result["steps"][0]["order"] == 1


async def test_escalate_incident_dry_run_returns_planned_action() -> None:
    result = await escalate_incident(
        customer_id="C-209",
        issue_type="duplicate_charge",
        severity="high",
        summary="Customer reports duplicate transaction.",
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["planned_action"]["target_team"] == "billing"


async def test_escalate_incident_non_dry_run_returns_error() -> None:
    result = await escalate_incident(
        customer_id="C-209",
        issue_type="duplicate_charge",
        severity="high",
        summary="Customer reports duplicate transaction.",
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["error"] == "Live escalation not available in POC"
