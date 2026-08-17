"""Dashboard URL configuration."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/", views.branch_dashboard, name="branch-dashboard"),
    path("dashboard/<str:branch_code>/", views.branch_dashboard, name="branch-dashboard-branch"),
    path("dashboard/coordinator/", views.coordinator_dashboard, name="coordinator-dashboard"),
    path("dashboard/gerente/", views.gerente_dashboard, name="gerente-dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin-dashboard"),
]
