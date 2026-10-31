from django.utils import timezone
from rest_framework import permissions, viewsets

from dashboard.models import PriceAlert, Share, Watchlist

from .serializers_watchlist import PriceAlertSerializer, WatchlistSerializer


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).select_related("share")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PriceAlertViewSet(viewsets.ModelViewSet):
    serializer_class = PriceAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PriceAlert.objects.filter(user=self.request.user).select_related("share")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
