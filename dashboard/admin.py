from django.contrib import admin

from dashboard.models import PriceAlert, Share, Watchlist


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("figi", "isin", "name", "ticker", "currency", "last_price", "is_trend_high", "updated_at")
    search_fields = ("figi", "isin", "name", "ticker")
    fields = (
        "figi",
        "isin",
        "name",
        "ticker",
        "currency",
        "uid",
        "last_price",
        "is_trend_high",
    )


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "share__ticker", "share__name")


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "target_price", "condition", "is_active", "is_triggered", "triggered_at", "created_at")
    list_filter = ("condition", "is_active", "is_triggered", "created_at")
    search_fields = ("user__username", "share__ticker", "share__name")
