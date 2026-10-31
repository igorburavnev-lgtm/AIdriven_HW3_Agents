from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import PriceAlertForm, WatchlistForm
from .models import PriceAlert, Watchlist


@login_required
def watchlist_list(request):
    items = Watchlist.objects.filter(user=request.user).select_related('share')
    return render(request, 'dashboard/watchlist.html', {'items': items})


@login_required
def watchlist_add(request):
    if request.method == 'POST':
        form = WatchlistForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect('dashboard:watchlist')
    else:
        form = WatchlistForm()
    return render(request, 'dashboard/watchlist_form.html', {'form': form})


@login_required
def watchlist_remove(request, pk):
    item = get_object_or_404(Watchlist, pk=pk, user=request.user)
    if request.method == 'POST':
        item.delete()
        return redirect('dashboard:watchlist')
    return render(request, 'dashboard/watchlist_remove.html', {'item': item})


@login_required
def alerts_list(request):
    alerts = PriceAlert.objects.filter(user=request.user).select_related('share')
    return render(request, 'dashboard/alerts.html', {'alerts': alerts})


@login_required
def alert_add(request):
    if request.method == 'POST':
        form = PriceAlertForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect('dashboard:alerts')
    else:
        form = PriceAlertForm()
    return render(request, 'dashboard/alert_form.html', {'form': form})


@login_required
def alert_remove(request, pk):
    alert = get_object_or_404(PriceAlert, pk=pk, user=request.user)
    if request.method == 'POST':
        alert.delete()
        return redirect('dashboard:alerts')
    return render(request, 'dashboard/alert_remove.html', {'alert': alert})
