"""Dashboard URL configuration."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/", views.branch_dashboard, name="branch-dashboard"),
    path("dashboard/<str:branch_code>/", views.branch_dashboard, name="branch-dashboard-branch"),
]
