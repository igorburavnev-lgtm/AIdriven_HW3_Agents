from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dashboard.models import Portfolio, Transaction
from dashboard.services import portfolio as portfolio_service

from .portfolio_serializer import (
    PortfolioSerializer,
    PositionSerializer,
    TradeInputSerializer,
    TransactionSerializer,
)


class PortfolioViewSet(viewsets.ModelViewSet):
    """Виртуальные портфели текущего пользователя.

    Unlike the public share catalogue (`/api/v1/shares/`), a portfolio is
    personal data: every endpoint requires authentication and the queryset is
    always filtered by the owner.
    """

    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Portfolio.objects.none()
        return Portfolio.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    # -- read-only views ---------------------------------------------------
    @action(detail=True, methods=["get"])
    def positions(self, request, pk=None):
        """Текущие позиции портфеля."""
        portfolio = self.get_object()
        queryset = portfolio.positions.select_related("share")
        return Response(PositionSerializer(queryset, many=True).data)

    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        """История операций портфеля."""
        portfolio = self.get_object()
        queryset = portfolio.transactions.select_related("share")
        page = self.paginate_queryset(queryset)
        serializer = TransactionSerializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Стоимость портфеля, прибыль и убытки."""
        return Response(portfolio_service.portfolio_summary(self.get_object()))

    # -- operations --------------------------------------------------------
    @action(detail=True, methods=["post"])
    def buy(self, request, pk=None):
        """Виртуальная покупка акций."""
        return self._trade(request, Transaction.Kind.BUY)

    @action(detail=True, methods=["post"])
    def sell(self, request, pk=None):
        """Виртуальная продажа акций."""
        return self._trade(request, Transaction.Kind.SELL)

    def _trade(self, request, kind: str) -> Response:
        portfolio = self.get_object()
        payload = TradeInputSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        try:
            transaction_obj = portfolio_service.execute_trade(
                portfolio=portfolio,
                share=data["share"],
                kind=kind,
                quantity=data["quantity"],
                price=data.get("price"),
                executed_at=data.get("executed_at"),
            )
        except portfolio_service.TradeError as exc:
            # Domain error -> 400 with a human readable message.
            raise ValidationError({"detail": str(exc)}) from exc

        position = portfolio.positions.filter(share=data["share"]).first()
        return Response(
            {
                "transaction": TransactionSerializer(transaction_obj).data,
                "position": PositionSerializer(position).data if position else None,
                "summary": portfolio_service.portfolio_summary(portfolio),
            },
            status=status.HTTP_201_CREATED,
        )
