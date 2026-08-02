"""Tests for the order mapper."""

from datetime import datetime
from typing import Any

from portal.services.mapper import map_order


def _raw_order(**overrides: Any) -> dict[str, Any]:
    """A minimal raw order; tests override only the part under test."""
    base: dict[str, Any] = {
        "order_number": "TEST-000",
        "email": "x@example.com",
        "recipient": "Test User",
        "zip": "00000",
        "street": "Test Street 1",
        "city": "Testville",
        "order_date": "2025-01-01T00:00:00Z",
        "articles": [],
    }
    base.update(overrides)
    return base


def _raw_article(**overrides: Any) -> dict[str, Any]:
    """A minimal raw article carrying none of the optional flag fields."""
    base: dict[str, Any] = {
        "sku": "BARE-SKU",
        "name": "Bare Article",
        "quantity": 1,
        "quantity_returned": 0,
        "price": 1.0,
    }
    base.update(overrides)
    return base


class TestMapOrderBasicFields:
    def test_order_number(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.order_number == "RMA-1001"

    def test_email(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.email == "alex@example.com"

    def test_recipient(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.recipient == "Jane Doe"

    def test_dates_parsed(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.order_date.year == 2025
        assert order.delivery_date.month == 12

    def test_article_count(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert len(order.articles) == 3


class TestMapArticleBasicFields:
    def test_sku(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.articles[0].sku == "TSHIRT-BLK-M"

    def test_name(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.articles[0].name == "T-Shirt Black M"

    def test_price(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.articles[0].price == 29.99

    def test_quantity(self, raw_order_1001: dict[str, Any]) -> None:
        order = map_order(raw_order_1001)
        assert order.articles[0].quantity == 2
        assert order.articles[0].quantity_returned == 0


class TestMapArticleMissingFields:
    def test_is_digital_flag(self, raw_order_1001: dict[str, Any]) -> None:
        """The E-Book should be flagged as a digital item."""
        order = map_order(raw_order_1001)
        ebook = order.articles[1]  # EBOOK-RETURNS
        assert ebook.is_digital is True

    def test_is_final_sale_flag(self, raw_order_1002: dict[str, Any]) -> None:
        """The Clearance Sneakers should be flagged as final sale."""
        order = map_order(raw_order_1002)
        shoes = order.articles[0]  # SHOES-CLR-42
        assert shoes.is_final_sale is True

    def test_category_apparel(self, raw_order_1001: dict[str, Any]) -> None:
        """The T-Shirt should have category 'apparel'."""
        order = map_order(raw_order_1001)
        tshirt = order.articles[0]  # TSHIRT-BLK-M
        assert tshirt.category == "apparel"

    def test_category_digital(self, raw_order_1001: dict[str, Any]) -> None:
        """The E-Book should have category 'digital'."""
        order = map_order(raw_order_1001)
        ebook = order.articles[1]  # EBOOK-RETURNS
        assert ebook.category == "digital"

    def test_is_digital_false_for_physical_item(
        self, raw_order_1001: dict[str, Any]
    ) -> None:
        """A physical t-shirt must not be flagged as digital."""
        order = map_order(raw_order_1001)
        tshirt = order.articles[0]  # TSHIRT-BLK-M
        assert tshirt.is_digital is False

    def test_is_final_sale_false_for_regular_item(
        self, raw_order_1001: dict[str, Any]
    ) -> None:
        """A regular item without final-sale markers should not be flagged."""
        order = map_order(raw_order_1001)
        tshirt = order.articles[0]  # TSHIRT-BLK-M
        assert tshirt.is_final_sale is False

    def test_is_final_sale_from_tags(self, raw_order_1002: dict[str, Any]) -> None:
        """final_sale key absent but 'final-sale' tag present — should be True."""
        order = map_order(raw_order_1002)
        shoes = order.articles[0]  # SHOES-CLR-42
        assert shoes.is_final_sale is True

    def test_category_from_product_type_fallback(
        self, raw_order_1002: dict[str, Any]
    ) -> None:
        """When no 'category' key exists, derive it from the first product_type segment."""
        order = map_order(raw_order_1002)
        shoes = order.articles[0]  # SHOES-CLR-42 — product_type="Footwear > Sneakers"
        assert shoes.category == "footwear"

    def test_category_empty_when_no_source(self) -> None:
        """An article with neither 'category' nor 'product_type' gets an empty string."""
        order = map_order(_raw_order(articles=[_raw_article()]))
        assert order.articles[0].category == ""


class TestUpstreamPayloadShape:
    """``orders_raw.json`` sends explicit flags rather than product_type/tags."""

    def test_explicit_category_is_used(
        self, raw_order_upstream: dict[str, Any]
    ) -> None:
        order = map_order(raw_order_upstream)
        assert [article.category for article in order.articles] == [
            "apparel",
            "digital",
            "footwear",
        ]

    def test_explicit_digital_flag_is_used(
        self, raw_order_upstream: dict[str, Any]
    ) -> None:
        order = map_order(raw_order_upstream)
        assert order.articles[1].is_digital is True

    def test_explicit_final_sale_flag_is_used(
        self, raw_order_upstream: dict[str, Any]
    ) -> None:
        order = map_order(raw_order_upstream)
        assert order.articles[2].is_final_sale is True

    def test_explicit_false_flags_are_respected(
        self, raw_order_upstream: dict[str, Any]
    ) -> None:
        order = map_order(raw_order_upstream)
        tshirt = order.articles[0]
        assert tshirt.is_digital is False
        assert tshirt.is_final_sale is False


class TestFlagPrecedence:
    """An explicit upstream key always beats a derived signal."""

    def test_explicit_category_beats_product_type(self) -> None:
        article = _raw_article(category="apparel", product_type="Digital > Books")
        order = map_order(_raw_order(articles=[article]))
        assert order.articles[0].category == "apparel"

    def test_explicit_final_sale_false_beats_final_sale_tag(self) -> None:
        article = _raw_article(final_sale=False, tags=["clearance", "final-sale"])
        order = map_order(_raw_order(articles=[article]))
        assert order.articles[0].is_final_sale is False

    def test_explicit_final_sale_true_without_any_tag(self) -> None:
        article = _raw_article(final_sale=True, tags=[])
        order = map_order(_raw_order(articles=[article]))
        assert order.articles[0].is_final_sale is True

    def test_digital_is_never_inferred_from_category(self) -> None:
        """A "digital" category holds physical goods too, so it must not imply digital."""
        article = _raw_article(category="digital", product_type="Digital > Cameras")
        order = map_order(_raw_order(articles=[article]))
        assert order.articles[0].is_digital is False


class TestDeliveryDateDerivation:
    def test_uses_the_most_recent_fulfillment(self) -> None:
        raw = _raw_order(
            fulfillments=[
                {"delivered_at": "2025-03-01T10:00:00Z"},
                {"delivered_at": "2025-03-05T10:00:00Z"},
                {"delivered_at": "2025-03-03T10:00:00Z"},
            ],
        )
        assert map_order(raw).delivery_date == datetime(2025, 3, 5, 10, 0)

    def test_ignores_fulfillments_without_a_delivery_date(self) -> None:
        raw = _raw_order(
            fulfillments=[
                {"carrier": "DHL", "tracking_number": "X"},
                {"delivered_at": "2025-03-02T10:00:00Z"},
            ],
        )
        assert map_order(raw).delivery_date == datetime(2025, 3, 2, 10, 0)

    def test_falls_back_to_top_level_delivered_at(self) -> None:
        raw = _raw_order(fulfillments=[], delivered_at="2025-04-01T08:00:00Z")
        assert map_order(raw).delivery_date == datetime(2025, 4, 1, 8, 0)

    def test_undelivered_order_falls_back_to_order_date(
        self, raw_order_1003: dict[str, Any]
    ) -> None:
        """Documents a known gap: the window starts counting before shipment.

        RMA-1003 has no fulfillments and no delivery date, so delivery_date
        collapses onto order_date.  See DECISIONS.md — fixing it needs delivery
        state on Order, not a mapper change.
        """
        order = map_order(raw_order_1003)
        assert order.delivery_date == order.order_date


class TestOrderFieldFallbacks:
    """Order-level fields fall back to the nested ``customer`` object."""

    def test_recipient_from_customer_names(self) -> None:
        raw = _raw_order(
            recipient="",
            customer={"first_name": "Ada", "last_name": "Lovelace"},
        )
        assert map_order(raw).recipient == "Ada Lovelace"

    def test_recipient_with_only_a_first_name(self) -> None:
        raw = _raw_order(recipient="", customer={"first_name": "Ada"})
        assert map_order(raw).recipient == "Ada"

    def test_street_joins_customer_address_lines(self) -> None:
        raw = _raw_order(
            street="",
            customer={
                "address_line": "Hauptstrasse 12",
                "address_line_extra": "Apt 4B",
            },
        )
        assert map_order(raw).street == "Hauptstrasse 12, Apt 4B"

    def test_street_without_an_extra_line(self) -> None:
        raw = _raw_order(street="", customer={"address_line": "Hauptstrasse 12"})
        assert map_order(raw).street == "Hauptstrasse 12"

    def test_zip_and_city_from_customer(self) -> None:
        raw = _raw_order(
            zip="",
            city="",
            customer={"postal_code": "10115", "city": "Berlin"},
        )
        order = map_order(raw)
        assert order.zip == "10115"
        assert order.city == "Berlin"

    def test_non_dict_customer_is_tolerated(self) -> None:
        raw = _raw_order(recipient="", customer="not-an-object")
        assert map_order(raw).recipient == ""


class TestMalformedPayloads:
    """The mapper coerces defensively rather than raising on bad upstream data."""

    def test_non_list_articles_yields_no_articles(self) -> None:
        assert map_order(_raw_order(articles="nope")).articles == []

    def test_non_dict_article_entries_are_skipped(self) -> None:
        raw = _raw_order(articles=[_raw_article(), "junk", 42, None])
        assert len(map_order(raw).articles) == 1

    def test_non_numeric_price_defaults_to_zero(self) -> None:
        raw = _raw_order(articles=[_raw_article(price="free")])
        assert map_order(raw).articles[0].price == 0.0

    def test_missing_quantity_defaults_to_one(self) -> None:
        article = _raw_article()
        del article["quantity"]
        assert map_order(_raw_order(articles=[article])).articles[0].quantity == 1

    def test_non_numeric_quantity_returned_defaults_to_zero(self) -> None:
        raw = _raw_order(articles=[_raw_article(quantity_returned="two")])
        assert map_order(raw).articles[0].quantity_returned == 0

    def test_numeric_sku_is_coerced_to_string(self) -> None:
        raw = _raw_order(articles=[_raw_article(sku=12345)])
        assert map_order(raw).articles[0].sku == "12345"
