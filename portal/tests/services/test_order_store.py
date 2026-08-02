"""Tests for the JSON-backed order store.

``find_order`` is the portal's credential check — it decides whether the
identifier a customer typed actually belongs to the order they asked for — so
its negative paths matter as much as its positive ones.
"""

from __future__ import annotations

from datetime import date

from portal.services.order_store import find_order, get_order


class TestFindOrder:
    """Lookup succeeds only when the identifier matches the order."""

    def test_matches_on_email(self) -> None:
        order = find_order("RMA-1001", "alex@example.com")
        assert order is not None
        assert order.order_number == "RMA-1001"

    def test_matches_on_zip(self) -> None:
        order = find_order("RMA-1001", "10115")
        assert order is not None
        assert order.order_number == "RMA-1001"

    def test_wrong_identifier_returns_none(self) -> None:
        assert find_order("RMA-1001", "wrong@example.com") is None

    def test_identifier_from_a_different_order_returns_none(self) -> None:
        """RMA-1002's email must not unlock RMA-1001."""
        assert find_order("RMA-1001", "lee@example.com") is None

    def test_unknown_order_number_returns_none(self) -> None:
        assert find_order("RMA-DOES-NOT-EXIST", "alex@example.com") is None

    def test_empty_identifier_returns_none(self) -> None:
        assert find_order("RMA-1001", "") is None


class TestGetOrder:
    """Retrieval by number, with no credential check."""

    def test_returns_mapped_order(self) -> None:
        order = get_order("RMA-1001")
        assert order is not None
        assert order.email == "alex@example.com"
        assert len(order.articles) == 2

    def test_unknown_order_number_returns_none(self) -> None:
        assert get_order("RMA-DOES-NOT-EXIST") is None


class TestFreshenDates:
    """Demo dates are re-anchored to today so the data stays realistic."""

    def test_delivery_is_anchored_to_configured_age(self) -> None:
        order = get_order("RMA-1001")
        assert order is not None
        assert (date.today() - order.delivery_date.date()).days == 5

    def test_gap_between_order_and_delivery_is_preserved(self) -> None:
        """Raw data has four days between purchase and delivery."""
        order = get_order("RMA-1001")
        assert order is not None
        assert (order.delivery_date - order.order_date).days == 4

    def test_older_order_is_anchored_further_back(self) -> None:
        order = get_order("RMA-1002")
        assert order is not None
        assert (date.today() - order.delivery_date.date()).days == 60
