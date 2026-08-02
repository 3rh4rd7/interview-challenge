"""Tests for the eligibility engine.

This is a starting point — not exhaustive.  You are expected to add tests
that cover your rules and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict, Unpack

import pytest

from portal.services.eligibility import (
    Rule,
    RuleConfigError,
    RulesConfig,
    evaluate_eligibility,
    load_rules,
)
from portal.types import Article, Order


class _ArticleData(TypedDict):
    sku: str
    name: str
    quantity: int
    quantity_returned: int
    price: float
    is_digital: bool
    is_final_sale: bool
    category: str


class _ArticleOverrides(TypedDict, total=False):
    sku: str
    name: str
    quantity: int
    quantity_returned: int
    price: float
    is_digital: bool
    is_final_sale: bool
    category: str


def _make_order(
    articles: list[Article],
    delivery_date: datetime | None = None,
) -> Order:
    return Order(
        order_number="TEST-001",
        email="test@example.com",
        recipient="Test User",
        zip="12345",
        street="Test Street 1",
        city="Testville",
        order_date=datetime(2025, 12, 1, 10, 0),
        delivery_date=delivery_date or datetime(2025, 12, 5, 14, 0),
        articles=articles,
    )


def _make_article(**overrides: Unpack[_ArticleOverrides]) -> Article:
    defaults: _ArticleData = {
        "sku": "TEST-SKU",
        "name": "Test Article",
        "quantity": 1,
        "quantity_returned": 0,
        "price": 19.99,
        "is_digital": False,
        "is_final_sale": False,
        "category": "general",
    }
    defaults.update(overrides)
    return Article(**defaults)


class TestDigitalItems:
    """Digital items should not be returnable."""

    def test_digital_item_is_not_returnable(self) -> None:
        order = _make_order(
            articles=[
                _make_article(sku="EBOOK-01", name="E-Book", is_digital=True),
            ]
        )
        results = evaluate_eligibility(order)
        assert results[0].returnable is False


class TestAlreadyReturned:
    """Fully returned items should not be returnable."""

    def test_fully_returned_is_not_returnable(self) -> None:
        order = _make_order(
            articles=[
                _make_article(quantity=1, quantity_returned=1),
            ]
        )
        results = evaluate_eligibility(order)
        assert results[0].returnable is False

    def test_partially_returned_is_still_returnable(self) -> None:
        """An item with remaining quantity should still be returnable."""
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article(quantity=3, quantity_returned=1)],
        )
        results = evaluate_eligibility(order)
        assert results[0].returnable is True


class TestReturnWindow:
    """Items past the return window should not be returnable."""

    def test_expired_window_is_not_returnable(self) -> None:
        """Delivery 100 days ago — clearly outside any reasonable window."""
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=100),
            articles=[_make_article()],
        )
        results = evaluate_eligibility(order)
        assert results[0].returnable is False

    def test_recent_delivery_is_returnable(self) -> None:
        """Delivery 5 days ago — well within a typical return window."""
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article()],
        )
        results = evaluate_eligibility(order)
        assert results[0].returnable is True


class TestRegularItem:
    """A regular, non-digital, non-final-sale item within the return window
    should be returnable."""

    def test_regular_item_is_returnable(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article()],
        )
        results = evaluate_eligibility(order)
        assert results[0].returnable is True


def _window_only_config(
    default_window_days: int = 30,
    category_window_days: dict[str, int] | None = None,
) -> RulesConfig:
    """A config with the window rule only, for isolating window behaviour."""
    return RulesConfig(
        version=1,
        default_window_days=default_window_days,
        category_window_days=category_window_days or {},
        rules=[
            Rule(
                id="window-expired",
                condition="window_expired",
                reason="The return window for this item has closed.",
            )
        ],
    )


class TestBlockingRuleMetadata:
    """A blocked article must say which rule blocked it, and why."""

    def test_returnable_item_has_no_reason_or_rule(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article()],
        )
        result = evaluate_eligibility(order)[0]
        assert result.returnable is True
        assert result.reason == ""
        assert result.matched_rule == ""

    def test_digital_item_matches_digital_rule(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article(is_digital=True)],
        )
        result = evaluate_eligibility(order)[0]
        assert result.matched_rule == "digital-item"
        assert result.reason != ""

    def test_final_sale_item_matches_final_sale_rule(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article(is_final_sale=True)],
        )
        result = evaluate_eligibility(order)[0]
        assert result.matched_rule == "final-sale"
        assert result.reason != ""

    def test_fully_returned_item_matches_already_returned_rule(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[_make_article(quantity=2, quantity_returned=2)],
        )
        result = evaluate_eligibility(order)[0]
        assert result.matched_rule == "already-returned"
        assert result.reason != ""

    def test_expired_window_matches_window_rule(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=100),
            articles=[_make_article()],
        )
        result = evaluate_eligibility(order)[0]
        assert result.matched_rule == "window-expired"
        assert result.reason != ""


class TestRulePrecedence:
    """When several rules match, the first one in the file wins.

    Intrinsic properties are ordered before the time-based window: an item
    that is final sale was never returnable, so saying "final sale" is more
    accurate than implying the customer was merely too late.
    """

    def test_final_sale_wins_over_expired_window(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=100),
            articles=[_make_article(is_final_sale=True)],
        )
        assert evaluate_eligibility(order)[0].matched_rule == "final-sale"

    def test_digital_wins_over_expired_window(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=100),
            articles=[_make_article(is_digital=True)],
        )
        assert evaluate_eligibility(order)[0].matched_rule == "digital-item"

    def test_already_returned_wins_over_digital(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=5),
            articles=[
                _make_article(quantity=1, quantity_returned=1, is_digital=True),
            ],
        )
        assert evaluate_eligibility(order)[0].matched_rule == "already-returned"


class TestReturnWindowBoundary:
    """The window is inclusive of its final day."""

    def test_last_day_of_window_is_returnable(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=30),
            articles=[_make_article()],
        )
        results = evaluate_eligibility(order, rules=_window_only_config(30))
        assert results[0].returnable is True

    def test_day_after_window_is_not_returnable(self) -> None:
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=31),
            articles=[_make_article()],
        )
        results = evaluate_eligibility(order, rules=_window_only_config(30))
        assert results[0].returnable is False


class TestCategoryWindows:
    """Per-category windows override the default; unlisted categories fall back."""

    def test_unknown_category_uses_default_window(self) -> None:
        config = _window_only_config(30, {"electronics": 14})
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=20),
            articles=[_make_article(category="apparel")],
        )
        assert evaluate_eligibility(order, rules=config)[0].returnable is True

    def test_category_override_shortens_window(self) -> None:
        config = _window_only_config(30, {"electronics": 14})
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=20),
            articles=[_make_article(category="electronics")],
        )
        assert evaluate_eligibility(order, rules=config)[0].returnable is False

    def test_category_override_lengthens_window(self) -> None:
        config = _window_only_config(14, {"apparel": 30})
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=20),
            articles=[_make_article(category="apparel")],
        )
        assert evaluate_eligibility(order, rules=config)[0].returnable is True


class TestRulesFileLoading:
    """The shipped file must load, and a broken one must fail loudly."""

    def test_shipped_rules_file_loads(self) -> None:
        config = load_rules()
        assert config.default_window_days == 30

    def test_shipped_rules_declare_expected_precedence(self) -> None:
        """Ordering is behaviour, so pin it."""
        assert [rule.id for rule in load_rules().rules] == [
            "already-returned",
            "digital-item",
            "final-sale",
            "window-expired",
        ]

    def test_unknown_condition_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.yaml"
        path.write_text(
            "version: 1\n"
            "default_window_days: 30\n"
            "rules:\n"
            "  - id: bogus\n"
            "    condition: no_such_condition\n"
            "    reason: nope\n",
            encoding="utf-8",
        )
        with pytest.raises(RuleConfigError, match="unknown condition"):
            load_rules(path)

    def test_malformed_yaml_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.yaml"
        path.write_text("version: 1\nrules: [unclosed\n", encoding="utf-8")
        with pytest.raises(RuleConfigError, match="not valid YAML"):
            load_rules(path)

    def test_missing_file_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(RuleConfigError, match="Cannot read"):
            load_rules(tmp_path / "does-not-exist.yaml")

    def test_non_mapping_root_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.yaml"
        path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(RuleConfigError, match="mapping at the top level"):
            load_rules(path)

    def test_schema_violation_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.yaml"
        path.write_text("version: 1\n", encoding="utf-8")
        with pytest.raises(RuleConfigError, match="expected schema"):
            load_rules(path)


class TestExplicitRules:
    def test_injected_rules_replace_the_shipped_file(self) -> None:
        """An empty rule set makes everything returnable, proving injection works."""
        no_rules = RulesConfig(version=1, default_window_days=30, rules=[])
        order = _make_order(
            delivery_date=datetime.now() - timedelta(days=500),
            articles=[_make_article(is_digital=True, is_final_sale=True)],
        )
        assert evaluate_eligibility(order, rules=no_rules)[0].returnable is True
