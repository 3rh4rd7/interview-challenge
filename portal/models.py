"""Auxiliary model dataclasses.

These are not Django ORM models. They represent return-registration shapes
used by rule evaluation and integration boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LineItem:
    sku: str
    name: str
    category: str | None
    quantity: int
    quantity_returned: int
    price: float
    is_digital: bool
    is_final_sale: bool


@dataclass(frozen=True)
class ReturnRegistration:
    order_number: str
    email: str
    zip: str
    purchased_at: datetime
    delivered_at: datetime
    return_window_days: int
    items: list[LineItem]


@dataclass(frozen=True)
class EligibilityResult:
    sku: str
    returnable: bool | None
    flag: str
    reason: str
    matched_rule_id: str | None
