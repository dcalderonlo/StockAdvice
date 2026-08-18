"""URL configuration for the onboarding app."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "onboarding"

urlpatterns = [
    path("", views.onboarding_status, name="status"),
    path("test-dms/", views.test_dms, name="test-dms"),
    path("backfill/", views.backfill, name="backfill"),
    path("test-run/", views.test_run, name="test-run"),
]
