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
def check_alerts():
    from django.utils import timezone
    from dashboard.models import PriceAlert
    alerts = PriceAlert.objects.filter(is_active=True, triggered=False).select_related('share', 'user')
    for alert in alerts:
        try:
            price = alert.share.last_price
            if price is None:
                continue
            hit = False
            if alert.condition == PriceAlert.ABOVE and float(price) >= float(alert.target_price):
                hit = True
            elif alert.condition == PriceAlert.BELOW and float(price) <= float(alert.target_price):
                hit = True
            if hit:
                alert.triggered = True
                alert.triggered_at = timezone.now()
                alert.save(update_fields=['triggered', 'triggered_at'])
                logger.info(f"Alert triggered: user={alert.user_id} share={alert.share.ticker} price={price}")
        except Exception as e:
            logger.error(e)
