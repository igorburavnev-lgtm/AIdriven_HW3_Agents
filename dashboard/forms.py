from django import forms
from .models import PriceAlert, Share, Watchlist


class ShareModelForm(forms.ModelForm):
    class Meta:
        model = Share
        fields = '__all__'


class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ('share',)


class PriceAlertForm(forms.ModelForm):
    class Meta:
        model = PriceAlert
        fields = ('share', 'target_price', 'condition')
