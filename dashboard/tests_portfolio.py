"""Tests for the virtual investment portfolio (task #4)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import Portfolio, Position, Share, Transaction
from dashboard.services.market_data import quotation_to_float

User = get_user_model()


def D(value) -> Decimal:
    """Normalise a JSON/serializer value (str | int | float) to Decimal."""
    return Decimal(str(value))


class PortfolioAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="trader@example.com",
            email="trader@example.com",
            password="Str0ngPass!23",
        )
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Str0ngPass!23",
        )
        self.share = Share.objects.create(
            figi="BBG004730N88",
            isin="RU0009029540",
            name="Сбербанк",
            ticker="SBER",
            currency="rub",
            uid="uid-sber",
            last_price=100.0,
            is_trend_high=True,
        )
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(owner=self.user, name="Основной")

    # -- helpers -----------------------------------------------------------
    def _url(self, action, portfolio=None):
        return f"/api/v1/portfolios/{(portfolio or self.portfolio).id}/{action}/"

    def _post_trade(self, action, quantity, price=None):
        payload = {"share": self.share.id, "quantity": str(quantity)}
        if price is not None:
            payload["price"] = str(price)
        return self.client.post(self._url(action), payload, format="json")

    def _buy(self, quantity, price=None):
        return self._post_trade("buy", quantity, price)

    def _sell(self, quantity, price=None):
        return self._post_trade("sell", quantity, price)

    # -- portfolio ---------------------------------------------------------
    def test_create_portfolio_assigns_current_user(self):
        response = self.client.post(
            "/api/v1/portfolios/", {"name": "Пенсионный"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        portfolio = Portfolio.objects.get(id=response.data["id"])
        self.assertEqual(portfolio.owner, self.user)

    def test_portfolio_list_is_scoped_to_owner(self):
        Portfolio.objects.create(owner=self.other_user, name="Чужой")

        response = self.client.get("/api/v1/portfolios/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["name"] for item in response.data["results"]], ["Основной"]
        )

    def test_duplicate_portfolio_name_is_rejected(self):
        response = self.client.post(
            "/api/v1/portfolios/", {"name": "Основной"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_user_cannot_access_foreign_portfolio(self):
        foreign = Portfolio.objects.create(owner=self.other_user, name="Чужой")

        response = self.client.get(f"/api/v1/portfolios/{foreign.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_endpoints_require_authentication(self):
        self.client.force_authenticate(None)

        response = self.client.get("/api/v1/portfolios/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    # -- buy ---------------------------------------------------------------
    def test_buy_creates_position_with_market_price(self):
        response = self._buy(10)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("10.000000"))
        self.assertEqual(position.avg_price, Decimal("100.000000"))
        self.assertEqual(response.data["transaction"]["kind"], Transaction.Kind.BUY)

    def test_second_buy_recalculates_weighted_average_price(self):
        self._buy(10, price=100)
        response = self._buy(10, price=200)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("20.000000"))
        self.assertEqual(position.avg_price, Decimal("150.000000"))
        self.assertEqual(Position.objects.count(), 1)

    def test_buy_rejects_non_positive_quantity(self):
        response = self._buy(0)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Position.objects.exists())

    def test_buy_without_price_and_without_market_data_is_rejected(self):
        self.share.last_price = None
        self.share.save(update_fields=["last_price"])

        response = self._buy(5)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Position.objects.exists())

    # -- sell --------------------------------------------------------------
    def test_sell_reduces_position_and_realizes_profit(self):
        self._buy(10, price=100)
        response = self._sell(4, price=150)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("6.000000"))
        self.assertEqual(position.avg_price, Decimal("100.000000"))
        self.assertEqual(
            D(response.data["transaction"]["realized_pnl"]), Decimal("200.000000")
        )

    def test_selling_more_than_held_is_rejected(self):
        self._buy(5, price=100)

        response = self._sell(10, price=120)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("5.000000"))
        self.assertEqual(Transaction.objects.filter(kind=Transaction.Kind.SELL).count(), 0)

    def test_selling_position_that_does_not_exist_is_rejected(self):
        response = self._sell(1, price=120)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Transaction.objects.exists())

    def test_full_sell_closes_position(self):
        self._buy(3, price=100)
        response = self._sell(3, price=110)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Position.objects.filter(portfolio=self.portfolio).exists())
        self.assertIsNone(response.data["position"])

    # -- valuation ---------------------------------------------------------
    def test_summary_computes_value_pnl_and_realized_result(self):
        self._buy(10, price=100)
        self._buy(10, price=200)     # avg 150, qty 20
        self._sell(5, price=250)     # realized +500, qty 15
        self.share.last_price = 250.0
        self.share.save(update_fields=["last_price"])

        response = self.client.get(self._url("summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(D(data["total_value"]), Decimal("3750.000000"))
        self.assertEqual(D(data["total_cost"]), Decimal("2250.000000"))
        self.assertEqual(D(data["unrealized_pnl"]), Decimal("1500.000000"))
        self.assertEqual(D(data["realized_pnl"]), Decimal("500.000000"))
        self.assertEqual(D(data["total_pnl"]), Decimal("2000.000000"))
        self.assertEqual(data["positions_count"], 1)
        self.assertEqual(data["unpriced_positions"], 0)

    def test_summary_marks_positions_without_price(self):
        self._buy(2, price=100)
        self.share.last_price = None
        self.share.save(update_fields=["last_price"])

        response = self.client.get(self._url("summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unpriced_positions"], 1)
        self.assertIsNone(response.data["positions"][0]["market_value"])
        self.assertEqual(D(response.data["total_value"]), Decimal("0"))

    # -- history -----------------------------------------------------------
    def test_transaction_history_lists_all_operations(self):
        self._buy(5, price=100)
        self._sell(2, price=120)

        response = self.client.get(self._url("transactions"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(
            [item["kind"] for item in results],
            [Transaction.Kind.SELL, Transaction.Kind.BUY],
        )

    def test_positions_endpoint_returns_current_positions(self):
        self._buy(7, price=100)

        response = self.client.get(self._url("positions"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["ticker"], "SBER")
        self.assertEqual(D(response.data[0]["quantity"]), Decimal("7.000000"))


class QuotationPrecisionTests(SimpleTestCase):
    """Regression for the price truncation defect (units without nano)."""

    class _Quotation:
        def __init__(self, units, nano):
            self.units = units
            self.nano = nano

    def test_fractional_part_is_preserved(self):
        self.assertAlmostEqual(
            quotation_to_float(self._Quotation(100, 550_000_000)), 100.55, places=9
        )

    def test_whole_numbers_stay_whole(self):
        self.assertAlmostEqual(quotation_to_float(self._Quotation(42, 0)), 42.0, places=9)
