from rest_framework import routers

from .portfolio_views import PortfolioViewSet
from .views import ShareViewSet

router = routers.DefaultRouter()
router.register(r"shares", ShareViewSet)
router.register(r"portfolios", PortfolioViewSet, basename="portfolio")
