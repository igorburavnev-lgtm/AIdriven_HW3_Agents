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


class Watchlist(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='watchlists')
    share = models.ForeignKey(Share, on_delete=models.CASCADE, related_name='watchlists')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'share')
        verbose_name = 'Список наблюдения'
        verbose_name_plural = 'Списки наблюдения'

    def __str__(self):
        return f"{self.user.username} - {self.share.ticker}"


class PriceAlert(models.Model):
    ABOVE = 'above'
    BELOW = 'below'
    CONDITION_CHOICES = ((ABOVE, '>= целевой'), (BELOW, '<= целевой'))

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='price_alerts')
    share = models.ForeignKey(Share, on_delete=models.CASCADE, related_name='price_alerts')
    target_price = models.FloatField()
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default=ABOVE)
    is_active = models.BooleanField(default=True)
    triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ценовой алерт'
        verbose_name_plural = 'Ценовые алерты'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} {self.share.ticker} {self.condition} {self.target_price}"
