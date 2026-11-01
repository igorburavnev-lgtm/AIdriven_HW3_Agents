from config.celery import app
from config.settings import logger
from dashboard.models import Share
from dashboard.services.market_data import get_last_data


@app.task
def update_last_price():
    """Refresh last_price and is_trend_high for every share."""
    for share in Share.objects.all():
        try:
            last_price, _price_time = get_last_data(share)
        except Exception as exc:  # noqa: BLE001 - one bad instrument must not stop the run
            logger.error("Failed to get price for share %s: %s", share.id, exc)
            continue

        if share.last_price is None:
            # First quote: nothing to compare with. The original relied on a
            # TypeError from `None > float` and logged an error on every run.
            is_trend_high = True
        else:
            is_trend_high = last_price >= share.last_price

        share.last_price = last_price
        share.is_trend_high = is_trend_high
        try:
            # QuerySet.update() bypasses auto_now, so updated_at stayed frozen;
            # save() keeps the "last updated" timestamp honest.
            share.save(update_fields=["last_price", "is_trend_high", "updated_at"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save price for share %s: %s", share.id, exc)
