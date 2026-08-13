"""Account URL routes for invitations, password reset, and account dashboard."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("dashboard/", views.account_dashboard, name="dashboard"),
    path("invite/", views.send_invitation, name="send_invitation"),
    path("invite/sent/", views.invitation_sent, name="invitation_sent"),
    path("invite/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path(
        "invite/<str:invitation_id>/resend/",
        views.resend_invitation_view,
        name="resend_invitation",
    ),
    path(
        "invite/<str:invitation_id>/revoke/",
        views.revoke_invitation_view,
        name="revoke_invitation",
    ),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path(
        "password-reset/", views.password_reset_request, name="password_reset_request"
    ),
    path(
        "password-reset/sent/",
        views.password_reset_sent,
        name="password_reset_sent",
    ),
    path(
        "password-reset/<str:token>/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.password_reset_complete,
        name="password_reset_complete",
    ),
]
