"""Business datatypes for the returns portal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """A single article (line item) in an order."""

    sku: str
    name: str
    quantity: int
    quantity_returned: int
    price: float

    is_digital: bool = False
    is_final_sale: bool = False
    category: str = ""


@dataclass
class Order:
    """A mapped customer order."""

    order_number: str
    email: str
    recipient: str
    zip: str
    street: str
    city: str
    order_date: datetime
    delivery_date: datetime
    articles: list[Article] = field(default_factory=list)


@dataclass
class ArticleEligibility:
    """Result of evaluating return eligibility for a single article."""

    article: Article
    returnable: bool
    reason: str  # human-readable explanation (empty string when returnable)
    matched_rule: str  # identifier of the rule that matched (empty when returnable)
