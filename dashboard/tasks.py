from config.celery import app
from dashboard.models import Share
from dashboard.services.market_data import get_last_data
from config.settings import logger


@app.task
def update_last_price():
    shares = Share.objects.all()

    for share in shares:
        try:
            result = get_last_data(share)
            if not result:
                continue
            last_price = result[0]

            try:
                if share.last_price is not None and last_price is not None:
                    if float(share.last_price) > float(last_price):
                        is_trend_high = False
                    else:
                        is_trend_high = True
                else:
                    is_trend_high = True
            except Exception as e:
                logger.error(e)
                is_trend_high = True

            try:
                Share.objects.filter(id=share.id).update(
                    last_price=last_price, is_trend_high=is_trend_high
                )
            except Exception as e:
                logger.error(e)
        except Exception as e:
            logger.error(e)



@app.task
def check_price_alerts():
    from django.utils import timezone

    from dashboard.models import PriceAlert

    alerts = PriceAlert.objects.filter(is_active=True, is_triggered=False).select_related(
        "share", "user"
    )
    for alert in alerts:
        try:
            share = alert.share
            price = share.last_price
            if price is None:
                continue
            triggered = False
            if alert.condition == PriceAlert.CONDITION_ABOVE and float(price) >= float(
                alert.target_price
            ):
                triggered = True
            elif alert.condition == PriceAlert.CONDITION_BELOW and float(price) <= float(
                alert.target_price
            ):
                triggered = True
            if triggered:
                alert.is_triggered = True
                alert.triggered_at = timezone.now()
                alert.save(update_fields=["is_triggered", "triggered_at"])
                logger.info(
                    f"Price alert triggered for user {alert.user_id} share {share.ticker} price {price}"
                )
        except Exception as e:
            logger.error(e)
