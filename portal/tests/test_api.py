from __future__ import annotations

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


class TestReturnsApiViewSet:
    def test_lookup_with_valid_credentials_returns_articles_url(self) -> None:
        client = APIClient()

        response = client.post(
            "/api/returns/lookup/",
            {
                "order_number": "RMA-1001",
                "identifier": "alex@example.com",
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["order_number"] == "RMA-1001"
        assert response.data["articles_url"].endswith("/api/returns/RMA-1001/articles/")

    def test_lookup_with_invalid_credentials_returns_400(self) -> None:
        client = APIClient()

        response = client.post(
            "/api/returns/lookup/",
            {
                "order_number": "RMA-1001",
                "identifier": "wrong@example.com",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "not found" in response.data["detail"].lower()

    def test_articles_requires_prior_lookup(self) -> None:
        client = APIClient()

        response = client.get("/api/returns/RMA-1001/articles/")

        assert response.status_code == 403

    def test_articles_after_lookup_returns_order_and_eligibility(self) -> None:
        client = APIClient()
        lookup_response = client.post(
            "/api/returns/lookup/",
            {
                "order_number": "RMA-1001",
                "identifier": "alex@example.com",
            },
            format="json",
        )
        assert lookup_response.status_code == 200

        response = client.get("/api/returns/RMA-1001/articles/")

        assert response.status_code == 200
        assert response.data["order"]["order_number"] == "RMA-1001"
        assert len(response.data["results"]) == 2

        first = response.data["results"][0]
        second = response.data["results"][1]
        assert first["article"]["sku"] == "TSHIRT-BLK-M"
        assert first["selectable"] is True
        assert first["quantity_options"] == [1]

        assert second["article"]["sku"] == "EBOOK-RETURNS"
        assert second["returnable"] is False
        assert second["selectable"] is False

    def test_lookup_requires_both_fields(self) -> None:
        client = APIClient()

        response = client.post(
            "/api/returns/lookup/",
            {"order_number": "RMA-1001"},
            format="json",
        )

        assert response.status_code == 400

    def test_articles_for_an_order_you_did_not_look_up_is_forbidden(self) -> None:
        """Was 404 before SEC-001.

        Authorization is now checked before the order is looked up, so an
        unknown order and another customer's order both return 403 rather than
        revealing which order numbers exist.  The 404 branch survives only for
        the case where the caller's *own* order vanishes from the store between
        lookup and this request.
        """
        client = APIClient()
        client.post(
            "/api/returns/lookup/",
            {"order_number": "RMA-1001", "identifier": "alex@example.com"},
            format="json",
        )

        response = client.get("/api/returns/RMA-NOPE/articles/")

        assert response.status_code == 403

    def test_blocked_article_reports_the_rule_that_blocked_it(self) -> None:
        client = APIClient()
        client.post(
            "/api/returns/lookup/",
            {"order_number": "RMA-1001", "identifier": "alex@example.com"},
            format="json",
        )

        response = client.get("/api/returns/RMA-1001/articles/")

        ebook = response.data["results"][1]
        assert ebook["matched_rule"] == "digital-item"
        assert ebook["reason"] != ""

    def test_returnable_article_reports_no_rule(self) -> None:
        client = APIClient()
        client.post(
            "/api/returns/lookup/",
            {"order_number": "RMA-1001", "identifier": "alex@example.com"},
            format="json",
        )

        response = client.get("/api/returns/RMA-1001/articles/")

        tshirt = response.data["results"][0]
        assert tshirt["returnable"] is True
        assert tshirt["matched_rule"] == ""
        assert tshirt["reason"] == ""


class TestCrossOrderAccess:
    """SEC-001: a session for one order must not unlock any other order.

    ``ReturnsViewSet.articles`` used to check only that *some* order number sat
    in the session, never that it matched the order being requested.  Any
    customer could therefore authenticate with an order they legitimately owned
    and then read every other order by number.  ``views.py`` always compared
    the two, so the browser flow was never affected -- the API was the outlier.

    See SECURITY.md.
    """

    def _authenticate_as_own_order(self) -> APIClient:
        """Log in legitimately as the owner of RMA-1001."""
        client = APIClient()
        response = client.post(
            "/api/returns/lookup/",
            {"order_number": "RMA-1001", "identifier": "alex@example.com"},
            format="json",
        )
        assert response.status_code == 200
        return client

    def test_cannot_read_another_customers_order(self) -> None:
        client = self._authenticate_as_own_order()

        response = client.get("/api/returns/RMA-1002/articles/")

        assert response.status_code == 403

    def test_does_not_leak_another_customers_personal_data(self) -> None:
        """The exploit's payoff was PII, so assert on the payload, not just the code."""
        client = self._authenticate_as_own_order()

        response = client.get("/api/returns/RMA-1002/articles/")
        body = response.content.decode()

        assert "Lee Schmidt" not in body
        assert "lee@example.com" not in body
        assert "Rosental 45" not in body
        assert "JACKET-GRN-L" not in body

    def test_own_order_is_still_reachable(self) -> None:
        """The fix must not break the legitimate path."""
        client = self._authenticate_as_own_order()

        response = client.get("/api/returns/RMA-1001/articles/")

        assert response.status_code == 200

    def test_unknown_order_is_indistinguishable_from_someone_elses(self) -> None:
        """No enumeration oracle: authorization is checked before existence.

        A caller must not be able to tell "this order exists but is not yours"
        (403) from "no such order" (404) -- that would confirm which order
        numbers are real.  Both return 403.
        """
        client = self._authenticate_as_own_order()

        someone_elses = client.get("/api/returns/RMA-1002/articles/")
        nonexistent = client.get("/api/returns/RMA-NOPE/articles/")

        assert someone_elses.status_code == nonexistent.status_code == 403
