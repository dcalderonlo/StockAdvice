"""Business services for invitations, email verification, and password reset."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.notifications.email import send_email

from .models import (
    INVITATION_EXPIRY_DAYS,
    EmailVerification,
    Invitation,
    PasswordReset,
    Role,
    User,
    UserRole,
)
from .tokens import TokenError


def create_invitation(
    invited_by: User,
    email: str,
    role_names: Iterable[str],
    branch_id: UUID | None = None,
) -> Invitation:
    """Create a pending invitation for a new user."""
    if not invited_by.tenant:
        raise ValueError("Inviter must belong to a tenant.")

    roles = list(Role.objects.filter(name__in=role_names))
    missing = set(role_names) - {r.name for r in roles}
    if missing:
        raise ValueError(f"Unknown roles: {missing}")

    invitation = Invitation.objects.create(
        email=email,
        invited_by=invited_by,
        tenant=invited_by.tenant,
        branch_id=branch_id,
    )
    invitation.roles.set(roles)
    return invitation


def send_invitation_email(invitation: Invitation, request) -> int:
    link = request.build_absolute_uri(
        reverse("accounts:accept_invitation", args=[str(invitation.token)])
    )
    return send_email(
        to_email=invitation.email,
        subject="Has sido invitado a StockAdvice",
        template_name="invitation",
        context={
            "invitation": invitation,
            "activation_link": link,
            "invited_by": invitation.invited_by,
        },
    )


@transaction.atomic
def accept_invitation(token: str, password: str) -> User:
    from .tokens import get_valid_invitation

    invitation = get_valid_invitation(token)
    tenant = invitation.tenant

    user, created = User.objects.get_or_create(
        email__iexact=invitation.email,
        defaults={"email": invitation.email.lower(), "tenant": tenant},
    )
    if not created and user.tenant_id != tenant.id:
        raise TokenError("This email is already associated with another tenant.")

    user.set_password(password)
    user.is_active = True
    user.save(update_fields=["password", "is_active"])

    for role in invitation.roles.all():
        UserRole.objects.get_or_create(
            user=user,
            role=role,
            defaults={"branch_id": invitation.branch_id},
        )

    invitation.status = Invitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at"])

    EmailVerification.objects.filter(user=user, verified_at__isnull=True).update(
        verified_at=timezone.now()
    )
    user.is_verified = True
    user.save(update_fields=["is_verified"])

    return user


@transaction.atomic
def resend_invitation(invitation: Invitation) -> None:
    if invitation.status != Invitation.Status.PENDING:
        raise ValueError("Only pending invitations can be resent.")
    invitation.expires_at = timezone.now() + timezone.timedelta(
        days=INVITATION_EXPIRY_DAYS
    )
    invitation.save(update_fields=["expires_at"])


@transaction.atomic
def revoke_invitation(invitation: Invitation) -> None:
    invitation.status = Invitation.Status.REVOKED
    invitation.save(update_fields=["status"])


@transaction.atomic
def create_email_verification(user: User) -> EmailVerification:
    EmailVerification.objects.filter(user=user, verified_at__isnull=True).delete()
    return EmailVerification.objects.create(user=user)


def send_verification_email(verification: EmailVerification, request) -> int:
    link = request.build_absolute_uri(
        reverse("accounts:verify_email", args=[str(verification.token)])
    )
    return send_email(
        to_email=verification.user.email,
        subject="Verifica tu correo electrónico - StockAdvice",
        template_name="email_verification",
        context={"verification": verification, "verification_link": link},
    )


@transaction.atomic
def verify_email(token: str) -> User:
    from .tokens import get_valid_email_verification

    verification = get_valid_email_verification(token)
    verification.verified_at = timezone.now()
    verification.save(update_fields=["verified_at"])

    user = verification.user
    user.is_verified = True
    user.save(update_fields=["is_verified"])
    return user


@transaction.atomic
def create_password_reset(email: str) -> PasswordReset | None:
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return None
    return PasswordReset.objects.create(user=user)


def send_password_reset_email(reset: PasswordReset, request) -> int:
    link = request.build_absolute_uri(
        reverse("accounts:password_reset_confirm", args=[str(reset.token)])
    )
    return send_email(
        to_email=reset.user.email,
        subject="Restablece tu contraseña - StockAdvice",
        template_name="password_reset",
        context={"reset": reset, "reset_link": link},
    )


@transaction.atomic
def reset_password(token: str, new_password: str) -> User:
    from .tokens import get_valid_password_reset

    reset = get_valid_password_reset(token)
    user = reset.user
    user.set_password(new_password)
    user.save(update_fields=["password"])

    reset.used_at = timezone.now()
    reset.save(update_fields=["used_at"])
    return user
