from rest_framework import serializers
from dashboard.models import PriceAlert, Watchlist
from .serializer import ShareSerializer


class WatchlistSerializer(serializers.ModelSerializer):
    share = ShareSerializer(read_only=True)
    share_id = serializers.PrimaryKeyRelatedField(source='share', queryset=__import__('dashboard.models', fromlist=['Share']).Share.objects.all(), write_only=True)

    class Meta:
        model = Watchlist
        fields = ['id', 'share', 'share_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class PriceAlertSerializer(serializers.ModelSerializer):
    share = ShareSerializer(read_only=True)
    share_id = serializers.PrimaryKeyRelatedField(source='share', queryset=__import__('dashboard.models', fromlist=['Share']).Share.objects.all(), write_only=True)

    class Meta:
        model = PriceAlert
        fields = ['id', 'share', 'share_id', 'target_price', 'condition', 'is_active', 'triggered', 'triggered_at', 'created_at']
        read_only_fields = ['id', 'triggered', 'triggered_at', 'created_at']
