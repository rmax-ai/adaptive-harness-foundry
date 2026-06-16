"""Incident playbook and escalation tools."""

from __future__ import annotations

import json
from pathlib import Path

_PLAYBOOKS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "incident_playbooks.json"


def _load_playbooks() -> list[dict]:
    try:
        with _PLAYBOOKS_PATH.open(encoding="utf-8") as data_file:
            playbooks: list[dict] = json.load(data_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return playbooks


async def get_incident_playbook(issue_type: str) -> dict:
    """Retrieve the incident playbook for a given issue type.

    Args:
        issue_type: The issue type whose playbook should be returned.

    Returns:
        The matching playbook payload, or a not-found payload when no playbook exists.
    """

    for playbook in _load_playbooks():
        if playbook.get("issue_type") == issue_type:
            return playbook

    return {"found": False, "issue_type": issue_type, "steps": []}


async def escalate_incident(
    customer_id: str,
    issue_type: str,
    severity: str,
    summary: str,
    dry_run: bool = True,
) -> dict:
    """Escalate an incident to the appropriate team.

    Args:
        customer_id: The affected customer identifier.
        issue_type: The incident category.
        severity: The requested severity level.
        summary: A short incident summary.
        dry_run: Whether to return only the planned escalation action.

    Returns:
        A dry-run plan by default, or an error payload for live escalation in the POC.
    """

    target_team = "billing" if "charge" in issue_type or "subscription" in issue_type else "support"
    planned_action = {
        "customer_id": customer_id,
        "issue_type": issue_type,
        "severity": severity,
        "summary": summary,
        "target_team": target_team,
    }

    if not dry_run:
        return {
            "ok": False,
            "error": "Live escalation not available in POC",
            "planned_action": planned_action,
        }

    return {
        "ok": True,
        "dry_run": True,
        "planned_action": planned_action,
    }
