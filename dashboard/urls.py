from django.urls import include, path

from dashboard.views import (
    PriceAlertCreateView,
    PriceAlertDeleteView,
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
    WatchlistCreateView,
    WatchlistDeleteView,
    WatchlistListView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("watchlist/", WatchlistListView.as_view(), name="watchlist"),
    path("watchlist/add/", WatchlistCreateView.as_view(), name="watchlist_add"),
    path("watchlist/delete/<int:pk>/", WatchlistDeleteView.as_view(), name="watchlist_delete"),
    path("alerts/", PriceAlertCreateView.as_view(), name="alerts"),
    path("alerts/delete/<int:pk>/", PriceAlertDeleteView.as_view(), name="alert_delete"),
    path("api/", include("dashboard.api.urls")),
]
