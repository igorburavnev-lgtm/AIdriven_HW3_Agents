from django.conf import settings
from django.db import models


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
        return self.ticker or self.name


class Watchlist(models.Model):
    """Персональный список наблюдения за акциями"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlists"
    )
    share = models.ForeignKey(Share, on_delete=models.CASCADE, related_name="watchlists")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Список наблюдения"
        verbose_name_plural = "Списки наблюдения"
        unique_together = ("user", "share")

    def __str__(self):
        return f"{self.user} - {self.share}"


class PriceAlert(models.Model):
    """Целевой уровень цены для уведомления"""

    CONDITION_ABOVE = "above"
    CONDITION_BELOW = "below"

    CONDITION_CHOICES = (
        (CONDITION_ABOVE, "Выше или равно"),
        (CONDITION_BELOW, "Ниже или равно"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="price_alerts"
    )
    share = models.ForeignKey(Share, on_delete=models.CASCADE, related_name="price_alerts")
    target_price = models.FloatField(verbose_name="Целевая цена")
    condition = models.CharField(
        max_length=10, choices=CONDITION_CHOICES, default=CONDITION_ABOVE
    )
    is_active = models.BooleanField(default=True)
    is_triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление о цене"
        verbose_name_plural = "Уведомления о цене"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.share.ticker} {self.condition} {self.target_price}"

