"""Token lookup and validation helpers for invitations and password resets."""

from __future__ import annotations

from uuid import UUID

from django.utils import timezone

from .models import EmailVerification, Invitation, PasswordReset


class TokenError(Exception):
    pass


class TokenExpired(TokenError):
    pass


class TokenUsed(TokenError):
    pass


def get_valid_invitation(token: str) -> Invitation:
    try:
        invitation = Invitation.objects.select_related("tenant").get(token=UUID(token))
    except (Invitation.DoesNotExist, ValueError) as exc:
        raise TokenError("Invalid invitation token.") from exc

    if invitation.status != Invitation.Status.PENDING:
        raise TokenUsed("This invitation has already been used or revoked.")
    if invitation.is_expired():
        invitation.mark_expired()
        raise TokenExpired("This invitation has expired.")
    return invitation


def get_valid_email_verification(token: str) -> EmailVerification:
    try:
        verification = EmailVerification.objects.select_related("user").get(
            token=UUID(token)
        )
    except (EmailVerification.DoesNotExist, ValueError) as exc:
        raise TokenError("Invalid verification token.") from exc

    if verification.verified_at:
        raise TokenUsed("This email has already been verified.")
    if verification.is_expired():
        raise TokenExpired("This verification link has expired.")
    return verification


def get_valid_password_reset(token: str) -> PasswordReset:
    try:
        reset = PasswordReset.objects.select_related("user").get(token=UUID(token))
    except (PasswordReset.DoesNotExist, ValueError) as exc:
        raise TokenError("Invalid password reset token.") from exc

    if reset.is_used():
        raise TokenUsed("This password reset link has already been used.")
    if reset.is_expired():
        raise TokenExpired("This password reset link has expired.")
    return reset


def build_absolute_link(request, path: str) -> str:
    return request.build_absolute_uri(path)
