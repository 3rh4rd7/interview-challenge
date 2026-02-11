"""Shared test fixtures and helpers."""

from __future__ import annotations

import pytest

RawOrder = dict[str, object]
RawArticle = dict[str, object]


def _make_raw_order(**overrides: object) -> dict[str, object]:
    """Create a raw order dict with sensible defaults."""
    base: RawOrder = {
        "order_number": "TEST-001",
        "email": "test@example.com",
        "recipient": "Test User",
        "zip": "12345",
        "street": "Test Street 1",
        "city": "Testville",
        "order_date": "2025-12-01T10:00:00Z",
        "fulfillments": [
            {
                "tracking_number": "TEST-TRACK-001",
                "carrier": "DHL",
                "delivered_at": "2025-12-05T14:00:00Z",
            },
        ],
        "articles": [],
    }
    base.update(overrides)
    return base


def _make_raw_article(**overrides: object) -> RawArticle:
    """Create a raw article dict with sensible defaults."""
    base: RawArticle = {
        "sku": "TEST-SKU",
        "name": "Test Article",
        "product_type": "General",
        "quantity": 1,
        "quantity_returned": 0,
        "price": 19.99,
        "requires_shipping": True,
        "tags": [],
    }
    base.update(overrides)
    return base


@pytest.fixture()
def raw_order_1001() -> RawOrder:
    """Raw payload matching order RMA-1001."""
    return _make_raw_order(
        order_number="RMA-1001",
        email="alex@example.com",
        zip="10115",
        recipient="Jane Doe",
        street="Luisenstrasse 12",
        city="Berlin",
        fulfillments=[
            {
                "tracking_number": "1Z999AA10123456784",
                "carrier": "DHL",
                "delivered_at": "2025-12-05T14:00:00Z",
            },
        ],
        articles=[
            _make_raw_article(
                sku="TSHIRT-BLK-M",
                name="T-Shirt Black M",
                product_type="Apparel > T-Shirts",
                quantity=2,
                price=29.99,
                tags=["summer-collection"],
            ),
            _make_raw_article(
                sku="EBOOK-RETURNS",
                name="Returns Best-Practices E-Book",
                product_type="Digital > Books",
                quantity=1,
                price=9.99,
                requires_shipping=False,
                tags=["digital-delivery"],
            ),
            _make_raw_article(
                sku="HOODIE-NAV-L",
                name="Navy Hoodie L",
                product_type="Apparel > Hoodies",
                quantity=1,
                price=59.99,
            ),
        ],
    )


@pytest.fixture()
def raw_order_1002() -> RawOrder:
    """Raw payload matching order RMA-1002."""
    return _make_raw_order(
        order_number="RMA-1002",
        email="max@example.com",
        zip="80331",
        recipient="Max Mustermann",
        street="Kapellenweg 6",
        city="München",
        order_date="2025-10-01T10:00:00Z",
        fulfillments=[
            {
                "tracking_number": "00340434161094042557",
                "carrier": "DHL",
                "delivered_at": "2025-10-05T14:00:00Z",
            },
        ],
        articles=[
            _make_raw_article(
                sku="SHOES-CLR-42",
                name="Clearance Sneakers 42",
                product_type="Footwear > Sneakers",
                price=49.99,
                tags=["clearance", "final-sale"],
            ),
            _make_raw_article(
                sku="JACKET-GRN-L",
                name="Green Jacket L",
                product_type="Apparel > Jackets",
                price=89.99,
                quantity_returned=1,
            ),
            _make_raw_article(
                sku="SCARF-RED",
                name="Red Wool Scarf",
                product_type="Accessories > Scarves",
                price=34.99,
                tags=["winter-collection"],
            ),
        ],
    )


@pytest.fixture()
def raw_order_1003() -> RawOrder:
    """Raw payload matching order RMA-1003 (no fulfillments)."""
    return _make_raw_order(
        order_number="RMA-1003",
        email="sam@example.com",
        zip="20144",
        recipient="Sam Rivera",
        street="Via Roma 42",
        city="Milano",
        order_date="2026-02-08T09:00:00Z",
        fulfillments=[],
        articles=[
            _make_raw_article(
                sku="GIFTCARD-50",
                name="Digital Gift Card \u20ac50",
                product_type="Gift Cards",
                quantity=1,
                price=50.00,
                requires_shipping=False,
                tags=["final-sale"],
            ),
            _make_raw_article(
                sku="PANTS-BLU-32",
                name="Blue Chinos 32",
                product_type="Apparel > Pants",
                quantity=1,
                price=69.99,
                tags=["clearance"],
            ),
        ],
    )
