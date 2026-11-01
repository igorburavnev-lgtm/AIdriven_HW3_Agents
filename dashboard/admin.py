from django.contrib import admin

from dashboard.models import Portfolio, Position, Share, Transaction


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("figi", "isin", "name", "ticker", "currency")
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


class PositionInline(admin.TabularInline):
    model = Position
    extra = 0
    readonly_fields = ("quantity", "avg_price")


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at", "updated_at")
    search_fields = ("name", "owner__username", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [PositionInline]


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "share", "quantity", "avg_price")
    search_fields = ("portfolio__name", "share__ticker")
    list_filter = ("portfolio",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "share", "kind", "quantity", "price", "realized_pnl", "executed_at")
    list_filter = ("kind", "portfolio")
    search_fields = ("portfolio__name", "share__ticker")
    readonly_fields = ("created_at",)
