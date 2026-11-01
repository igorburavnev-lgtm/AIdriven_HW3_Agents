import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()


app.conf.beat_schedule = {
    "update-last-price": {
        "task": "dashboard.tasks.update_last_price",
        # Interval is configured by PRICE_UPDATE_INTERVAL_SECONDS (default 5 min).
        "schedule": float(getattr(settings, "PRICE_UPDATE_INTERVAL_SECONDS", 300)),
    },
}
