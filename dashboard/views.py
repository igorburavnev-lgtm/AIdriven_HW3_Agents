from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import PriceAlertForm, ShareModelForm, WatchlistForm
from .models import PriceAlert, Share, Watchlist
from .services.graph import get_graph


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect("dashboard:index")


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, id=pk)

        try:
            plot_div = get_graph(share)
        except Exception:
            plot_div = None

        return render(
            request,
            "dashboard/detail.html",
            {"plot_div": plot_div, "share": share},
        )


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareUpdateView(IsUserAuthenticatedMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(IsUserAuthenticatedMixin, DeleteView):
    """Удаление акции"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")


class WatchlistListView(LoginRequiredMixin, ListView):
    model = Watchlist
    template_name = "dashboard/watchlist.html"
    context_object_name = "items"

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).select_related("share")


class WatchlistCreateView(LoginRequiredMixin, CreateView):
    model = Watchlist
    form_class = WatchlistForm
    template_name = "dashboard/watchlist_add.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class WatchlistDeleteView(LoginRequiredMixin, DeleteView):
    model = Watchlist
    template_name = "dashboard/watchlist_delete.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)


class PriceAlertCreateView(LoginRequiredMixin, CreateView, ListView):
    model = PriceAlert
    form_class = PriceAlertForm
    template_name = "dashboard/alerts.html"
    success_url = reverse_lazy("dashboard:alerts")
    context_object_name = "alerts"

    def get_queryset(self):
        return PriceAlert.objects.filter(user=self.request.user).select_related("share")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class PriceAlertDeleteView(LoginRequiredMixin, DeleteView):
    model = PriceAlert
    template_name = "dashboard/alert_delete.html"
    success_url = reverse_lazy("dashboard:alerts")

    def get_queryset(self):
        return PriceAlert.objects.filter(user=self.request.user)
