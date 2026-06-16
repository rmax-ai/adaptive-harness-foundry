"""Registry of plain async tools for ADK agent construction."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from harness_foundry.tools.customers import get_customer
from harness_foundry.tools.incidents import escalate_incident, get_incident_playbook
from harness_foundry.tools.policies import (
    calculate_refund_eligibility,
    search_policy,
)
from harness_foundry.tools.transactions import get_transactions

ToolCallable = Callable[..., Awaitable[dict[str, Any]]]


def get_all_tools() -> list[ToolCallable]:
    """Return all registered tools for use with ``LlmAgent(tools=...)``."""

    return [
        get_customer,
        get_transactions,
        search_policy,
        calculate_refund_eligibility,
        get_incident_playbook,
        escalate_incident,
    ]
