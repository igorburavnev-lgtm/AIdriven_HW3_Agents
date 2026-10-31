from rest_framework import serializers

from dashboard.models import PriceAlert, Share, Watchlist


class WatchlistSerializer(serializers.ModelSerializer):
    share_detail = serializers.SerializerMethodField()

    class Meta:
        model = Watchlist
        fields = ("id", "user", "share", "share_detail", "created_at")
        read_only_fields = ("user", "created_at")

    def get_share_detail(self, obj):
        from .serializer import ShareSerializer

        return ShareSerializer(obj.share).data


class PriceAlertSerializer(serializers.ModelSerializer):
    share_detail = serializers.SerializerMethodField()

    class Meta:
        model = PriceAlert
        fields = (
            "id",
            "user",
            "share",
            "share_detail",
            "target_price",
            "condition",
            "is_active",
            "is_triggered",
            "triggered_at",
            "created_at",
        )
        read_only_fields = ("user", "is_triggered", "triggered_at", "created_at")

    def get_share_detail(self, obj):
        from .serializer import ShareSerializer

        return ShareSerializer(obj.share).data
