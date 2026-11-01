from decimal import Decimal

from rest_framework import serializers

from dashboard.models import Portfolio, Position, Share, Transaction
from dashboard.services import portfolio as portfolio_service


class PortfolioSerializer(serializers.ModelSerializer):
    positions_count = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = ("id", "name", "created_at", "updated_at", "positions_count")
        read_only_fields = ("id", "created_at", "updated_at", "positions_count")

    def get_positions_count(self, obj) -> int:
        return obj.positions.count()

    def validate_name(self, value):
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            # (owner, name) is unique; check it here so the API answers 400
            # instead of failing on the database constraint.
            existing = Portfolio.objects.filter(owner=request.user, name=value)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    "Портфель с таким названием уже существует"
                )
        return value


class PositionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    name = serializers.CharField(source="share.name", read_only=True)
    currency = serializers.CharField(source="share.currency", read_only=True)
    current_price = serializers.SerializerMethodField()
    market_value = serializers.SerializerMethodField()
    cost_basis = serializers.DecimalField(
        max_digits=18, decimal_places=6, read_only=True
    )
    unrealized_pnl = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = (
            "id",
            "share",
            "ticker",
            "name",
            "currency",
            "quantity",
            "avg_price",
            "cost_basis",
            "current_price",
            "market_value",
            "unrealized_pnl",
        )
        read_only_fields = fields

    def get_current_price(self, obj):
        return portfolio_service.share_price(obj.share)

    def get_market_value(self, obj):
        price = portfolio_service.share_price(obj.share)
        return None if price is None else price * obj.quantity

    def get_unrealized_pnl(self, obj):
        price = portfolio_service.share_price(obj.share)
        return None if price is None else price * obj.quantity - obj.cost_basis


class TransactionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "share",
            "ticker",
            "kind",
            "kind_display",
            "quantity",
            "price",
            "realized_pnl",
            "executed_at",
            "created_at",
        )
        read_only_fields = fields


class TradeInputSerializer(serializers.Serializer):
    """Input of the buy/sell actions."""

    share = serializers.PrimaryKeyRelatedField(queryset=Share.objects.all())
    quantity = serializers.DecimalField(
        max_digits=18, decimal_places=6, min_value=Decimal("0.000001")
    )
    price = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=Decimal("0.000001"),
        required=False,
        allow_null=True,
        help_text="Цена за единицу. Если не указана, используется последняя рыночная цена.",
    )
    executed_at = serializers.DateTimeField(required=False, allow_null=True)
