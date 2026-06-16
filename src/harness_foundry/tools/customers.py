"""Customer lookup tools."""

from __future__ import annotations

import json
from pathlib import Path

_CUSTOMERS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "customers.json"


def _load_customers() -> list[dict]:
    try:
        with _CUSTOMERS_PATH.open(encoding="utf-8") as data_file:
            customers: list[dict] = json.load(data_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return customers


async def get_customer(customer_id: str) -> dict:
    """Retrieve customer information by ID.

    Args:
        customer_id: The customer identifier to look up.

    Returns:
        The matching customer record, or a not-found payload when no customer exists.
    """

    for customer in _load_customers():
        if customer.get("id") == customer_id:
            return customer

    return {"found": False, "customer_id": customer_id}
