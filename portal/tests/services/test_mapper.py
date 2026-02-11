"""Tests for the order mapper."""

from typing import Any

from portal.services.mapper import map_order


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
