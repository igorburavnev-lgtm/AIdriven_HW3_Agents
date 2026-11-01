from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True)
    isin = models.CharField(max_length=255)
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(max_length=255, unique=True)
    last_price = models.FloatField(blank=True, null=True, verbose_name="Текущая цена")
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"

    def __str__(self):
        return f"{self.ticker} ({self.name})"


class Portfolio(models.Model):
    """Виртуальный инвестиционный портфель пользователя."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
        verbose_name="Владелец",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Портфель"
        verbose_name_plural = "Портфели"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="uniq_portfolio_owner_name"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.owner})"


class Position(models.Model):
    """Текущая позиция портфеля по одной бумаге."""

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.PROTECT,
        related_name="positions",
        verbose_name="Акция",
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Количество",
    )
    avg_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0"),
        verbose_name="Средняя цена приобретения",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Позиция"
        verbose_name_plural = "Позиции"
        ordering = ["share__ticker"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "share"], name="uniq_position_portfolio_share"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="position_quantity_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.share.ticker}: {self.quantity} @ {self.avg_price}"

    @property
    def cost_basis(self) -> Decimal:
        """Book value of the position at its average purchase price."""
        return self.avg_price * self.quantity


class Transaction(models.Model):
    """История виртуальных операций покупки и продажи."""

    class Kind(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Акция",
    )
    kind = models.CharField(
        max_length=4, choices=Kind.choices, verbose_name="Тип операции"
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Количество",
    )
    price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Цена за единицу",
    )
    realized_pnl = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0"),
        verbose_name="Реализованный финансовый результат",
    )
    executed_at = models.DateTimeField(
        default=timezone.now, verbose_name="Время операции"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Операция"
        verbose_name_plural = "Операции"
        ordering = ["-executed_at", "-id"]

    def __str__(self):
        return (
            f"{self.get_kind_display()} {self.quantity} "
            f"{self.share.ticker} @ {self.price}"
        )
