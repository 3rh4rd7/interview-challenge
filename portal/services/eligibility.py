"""Return eligibility engine.

Rules live in ``portal/data/return_rules.yaml`` rather than in code, so the
returns team can change a window or reword a customer-facing message without a
deploy.  The file is a *deny list*: each rule names a reason to block a return,
and an article matching no rule is returnable.

Rules are evaluated in file order and the first match wins, so the ordering in
the YAML is the precedence.  Each rule's ``condition`` names a predicate in
:data:`_CONDITIONS`; keeping the vocabulary closed means a typo in the config
is caught when the file loads instead of quietly making an article returnable.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from portal.types import Article, ArticleEligibility, Order

_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "return_rules.yaml"


class RuleConfigError(Exception):
    """The rules file is missing, malformed, or references an unknown condition."""


class Rule(BaseModel):
    """A single blocking rule."""

    id: str
    condition: str
    reason: str


class RulesConfig(BaseModel):
    """Parsed contents of the rules file."""

    version: int
    default_window_days: int = Field(ge=0)
    category_window_days: dict[str, Annotated[int, Field(ge=0)]] = Field(
        default_factory=dict
    )
    rules: list[Rule]

    @field_validator("category_window_days")
    @classmethod
    def _normalise_keys(cls, value: dict[str, int]) -> dict[str, int]:
        """Match the normalisation the mapper applies to ``Article.category``.

        The file is hand-edited, so a key written as "Electronics" must still
        match an article whose category is "electronics" — otherwise the entry
        silently never applies.
        """
        return {key.strip().lower(): days for key, days in value.items()}

    def window_days_for(self, category: str) -> int:
        """Return the window for *category*, falling back to the default.

        *category* is normalised on the way in as well.  ``map_order`` already
        produces canonical values, but nothing in the type system enforces
        that, and a mismatch here fails silently by applying the default window
        rather than raising.
        """
        key = category.strip().lower()
        return self.category_window_days.get(key, self.default_window_days)


def _fully_returned(
    article: Article, order: Order, config: RulesConfig, today: date
) -> bool:
    return article.quantity_returned >= article.quantity


def _is_digital(
    article: Article, order: Order, config: RulesConfig, today: date
) -> bool:
    return article.is_digital


def _is_final_sale(
    article: Article, order: Order, config: RulesConfig, today: date
) -> bool:
    return article.is_final_sale


def _window_expired(
    article: Article, order: Order, config: RulesConfig, today: date
) -> bool:
    """True once more than ``window_days`` have passed since delivery.

    Compared at day granularity, and inclusive of the final day: a 30-day
    window is still open on day 30 and closes on day 31.  Using dates rather
    than timestamps avoids a window that expires part-way through its last day.
    """
    window_days = config.window_days_for(article.category)
    days_since_delivery = (today - order.delivery_date.date()).days
    return days_since_delivery > window_days


Predicate = Callable[[Article, Order, RulesConfig, date], bool]

#: Vocabulary available to the ``condition`` field in the rules file.
_CONDITIONS: dict[str, Predicate] = {
    "fully_returned": _fully_returned,
    "is_digital": _is_digital,
    "is_final_sale": _is_final_sale,
    "window_expired": _window_expired,
}


def load_rules(path: Path | None = None) -> RulesConfig:
    """Load and validate the rules file.

    Raises:
        RuleConfigError: if the file cannot be read, is not valid YAML, does
            not match the expected schema, or names an unknown condition.
    """
    rules_path = path or _RULES_PATH
    document = _read_yaml_mapping(rules_path)
    config = _build_config(document, rules_path)
    _reject_unknown_conditions(config, rules_path)
    return config


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    """Read *path* as YAML and confirm it holds a mapping."""
    try:
        with path.open(encoding="utf-8") as handle:
            document: object = yaml.safe_load(handle)
    except OSError as exc:
        raise RuleConfigError(f"Cannot read rules file at {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RuleConfigError(f"Rules file at {path} is not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise RuleConfigError(
            f"Rules file at {path} must contain a mapping at the top level."
        )

    return document


def _build_config(document: dict[str, object], path: Path) -> RulesConfig:
    """Validate a raw mapping against the config schema."""
    try:
        return RulesConfig.model_validate(document)
    except ValidationError as exc:
        raise RuleConfigError(
            f"Rules file at {path} does not match the expected schema: {exc}"
        ) from exc


def _reject_unknown_conditions(config: RulesConfig, path: Path) -> None:
    """Fail if any rule names a condition with no registered predicate."""
    unknown = sorted(
        {rule.condition for rule in config.rules if rule.condition not in _CONDITIONS}
    )
    if not unknown:
        return

    raise RuleConfigError(
        f"Rules file at {path} references unknown condition(s): "
        f"{', '.join(unknown)}. Known conditions: {', '.join(sorted(_CONDITIONS))}."
    )


@lru_cache(maxsize=1)
def _default_rules() -> RulesConfig:
    """Load the shipped rules file once per process."""
    return load_rules()


def evaluate_eligibility(
    order: Order, rules: RulesConfig | None = None
) -> list[ArticleEligibility]:
    """Evaluate return eligibility for every article in *order*.

    Args:
        order: the order whose articles should be evaluated.
        rules: rules to apply.  Defaults to the shipped rules file; tests pass
            an explicit config to stay independent of it.

    Returns:
        A list of :class:`ArticleEligibility`, one per article in the order.
    """
    config = rules if rules is not None else _default_rules()
    today = date.today()
    return [
        _evaluate_article(article, order, config, today) for article in order.articles
    ]


def _evaluate_article(
    article: Article, order: Order, config: RulesConfig, today: date
) -> ArticleEligibility:
    for rule in config.rules:
        if _CONDITIONS[rule.condition](article, order, config, today):
            return ArticleEligibility(
                article=article,
                returnable=False,
                reason=rule.reason,
                matched_rule=rule.id,
            )

    return ArticleEligibility(
        article=article,
        returnable=True,
        reason="",
        matched_rule="",
    )
