"""Transaction lookup tools."""

from __future__ import annotations

import json
from pathlib import Path

_TRANSACTIONS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "transactions.json"


def _load_transactions() -> list[dict]:
    try:
        with _TRANSACTIONS_PATH.open(encoding="utf-8") as data_file:
            transactions: list[dict] = json.load(data_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return transactions


async def get_transactions(customer_id: str) -> dict:
    """Retrieve all transactions for a customer.

    Args:
        customer_id: The customer identifier whose transactions should be returned.

    Returns:
        A payload containing the customer ID and a list of matching transactions.
    """

    transactions = [
        transaction
        for transaction in _load_transactions()
        if transaction.get("customer_id") == customer_id
    ]
    return {"customer_id": customer_id, "transactions": transactions}
