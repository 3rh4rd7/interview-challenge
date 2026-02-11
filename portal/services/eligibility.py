"""Return eligibility engine."""

from __future__ import annotations

from portal.types import ArticleEligibility, Order


def evaluate_eligibility(order: Order) -> list[ArticleEligibility]:
    """Evaluate return eligibility for every article in *order*.

    Returns:
        A list of :class:`ArticleEligibility`, one per article in the order.
    """
    return [
        ArticleEligibility(
            article=article,
            returnable=True,
            reason="",
            matched_rule="",
        )
        for article in order.articles
    ]
