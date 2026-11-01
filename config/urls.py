from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    # Trailing slash for consistency with the other mount points; the resulting
    # URLs (/user/login/ etc.) are unchanged because user/urls.py uses "login/".
    path("user/", include("user.urls")),
]
