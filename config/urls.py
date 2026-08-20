"""Root URL configuration for StockAdvice."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.core.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(template_name="accounts/logout.html"), name="logout"),
    path("accounts/password-change/", auth_views.PasswordChangeView.as_view(template_name="accounts/password_reset_confirm.html"), name="password_change"),
    path("accounts/password-change/done/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/allauth/", include("allauth.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
    path("health/", health_check, name="health-check"),
    path("", include("apps.dashboard.urls")),
]
