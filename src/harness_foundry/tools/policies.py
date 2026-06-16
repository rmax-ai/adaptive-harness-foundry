"""Policy search and refund eligibility tools."""

from __future__ import annotations

import json
from pathlib import Path

_POLICIES_PATH = Path(__file__).parent.parent.parent.parent / "data" / "policies.json"
_REFUND_DAY_LIMITS = {
    "enterprise": 30,
    "premium": 21,
    "basic": 7,
}


def _load_policies() -> list[dict]:
    try:
        with _POLICIES_PATH.open(encoding="utf-8") as data_file:
            policies: list[dict] = json.load(data_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return policies


async def search_policy(query: str) -> dict:
    """Search policy documents by keyword.

    Args:
        query: The case-insensitive keyword to search for in policy text.

    Returns:
        A payload containing the query and the matching policy documents.
    """

    normalized_query = query.casefold()
    matches = [
        policy
        for policy in _load_policies()
        if normalized_query in str(policy.get("text", "")).casefold()
    ]
    return {"query": query, "policies": matches}


async def calculate_refund_eligibility(days_since_purchase: int, customer_tier: str) -> dict:
    """Calculate whether a refund is eligible based on days since purchase and tier.

    Args:
        days_since_purchase: Number of days elapsed since the original purchase.
        customer_tier: The customer's service tier.

    Returns:
        A payload describing refund eligibility under the tier-specific refund policy.
    """

    normalized_tier = customer_tier.casefold()
    days_limit = _REFUND_DAY_LIMITS.get(normalized_tier, 0)
    policy_section = {
        "enterprise": "POL-REFUND-02",
        "premium": "POL-REFUND-03",
        "basic": "POL-REFUND-04",
    }.get(normalized_tier, "POL-REFUND-01")
    eligible = days_since_purchase <= days_limit
    exception_possible = normalized_tier in {"enterprise", "premium"} and not eligible

    return {
        "eligible": eligible,
        "policy_section": policy_section,
        "days_limit": days_limit,
        "exception_possible": exception_possible,
    }
