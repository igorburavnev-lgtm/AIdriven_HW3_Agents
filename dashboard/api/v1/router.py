from rest_framework import routers

from .views import *
from .views_ext import PriceAlertViewSet, WatchlistViewSet

router = routers.DefaultRouter()
router.register(r"shares", ShareViewSet)
router.register(r"watchlist", WatchlistViewSet, basename="watchlist")
router.register(r"alerts", PriceAlertViewSet, basename="alerts")

