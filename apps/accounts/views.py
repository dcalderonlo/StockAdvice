"""Account views: profile, invitation acceptance, email verification, password reset."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .forms import (
    AcceptInvitationForm,
    AccountDashboardForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
)
from .models import Invitation
from .permissions import get_branch_scope, get_user_roles, require_any_role
from .tokens import TokenError, TokenExpired, TokenUsed, get_valid_invitation, get_valid_password_reset


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return HttpResponse(f"Logged in as {request.user.email}")


@login_required
def account_dashboard(request: HttpRequest) -> HttpResponse:
    form = AccountDashboardForm(instance=request.user)
    if request.method == "POST":
        form = AccountDashboardForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado.")
            return redirect("accounts:dashboard")

    return render(
        request,
        "accounts/account_dashboard.html",
        {
            "form": form,
            "roles": get_user_roles(request.user),
            "branch_scope": get_branch_scope(request.user),
        },
    )


def accept_invitation(request: HttpRequest, token: str) -> HttpResponse:
    try:
        invitation_obj = get_valid_invitation(token)
    except (TokenError, TokenExpired, TokenUsed) as exc:
        return render(request, "accounts/invitation_invalid.html", {"reason": str(exc)})

    form = AcceptInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.accept_invitation(token, form.cleaned_data["password"])
            return render(request, "accounts/invitation_accepted.html")
        except TokenError as exc:
            form.add_error(None, str(exc))

    return render(
        request,
        "accounts/accept_invitation.html",
        {"form": form, "invitation": invitation_obj},
    )


def verify_email(request: HttpRequest, token: str) -> HttpResponse:
    try:
        services.verify_email(token)
        return render(request, "accounts/email_verified.html")
    except (TokenError, TokenExpired, TokenUsed) as exc:
        return render(
            request, "accounts/email_verification_invalid.html", {"reason": str(exc)}
        )


def password_reset_request(request: HttpRequest) -> HttpResponse:
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reset = services.create_password_reset(form.cleaned_data["email"])
        if reset:
            services.send_password_reset_email(reset, request)
        return redirect("accounts:password_reset_sent")
    return render(request, "accounts/password_reset_request.html", {"form": form})


def password_reset_sent(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/password_reset_sent.html")


def password_reset_confirm(request: HttpRequest, token: str) -> HttpResponse:
    try:
        reset = get_valid_password_reset(token)
    except (TokenError, TokenExpired, TokenUsed) as exc:
        return render(
            request, "accounts/password_reset_invalid.html", {"reason": str(exc)}
        )

    form = PasswordResetConfirmForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.reset_password(token, form.cleaned_data["new_password"])
        return redirect("accounts:password_reset_complete")
    return render(
        request, "accounts/password_reset_confirm.html", {"form": form, "reset": reset}
    )


def password_reset_complete(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/password_reset_complete.html")


@require_any_role("administrator", "gerente", "warehouse_coordinator")
def send_invitation(request: HttpRequest) -> HttpResponse:
    from .forms import InvitationForm

    form = InvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invitation = services.create_invitation(
            invited_by=request.user,
            email=form.cleaned_data["email"],
            role_names=[r.name for r in form.cleaned_data["roles"]],
            branch_id=form.cleaned_data.get("branch_id"),
        )
        services.send_invitation_email(invitation, request)
        return redirect("accounts:invitation_sent")
    return render(request, "accounts/send_invitation.html", {"form": form})


def invitation_sent(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/invitation_sent.html")


@require_any_role("administrator", "gerente", "warehouse_coordinator")
def resend_invitation_view(request: HttpRequest, invitation_id: str) -> HttpResponse:
    invitation = get_object_or_404(Invitation, id=invitation_id)
    services.resend_invitation(invitation)
    services.send_invitation_email(invitation, request)
    messages.success(request, "Invitación reenviada.")
    return redirect("admin:accounts_invitation_changelist")


@require_any_role("administrator", "gerente", "warehouse_coordinator")
def revoke_invitation_view(request: HttpRequest, invitation_id: str) -> HttpResponse:
    invitation = get_object_or_404(Invitation, id=invitation_id)
    services.revoke_invitation(invitation)
    messages.success(request, "Invitación revocada.")
    return redirect("admin:accounts_invitation_changelist")
