"""Forms for invitations, password reset, and account dashboard."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import Invitation, Role, User


class InvitationForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
    )
    branch_id = forms.UUIDField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Invitation
        fields = ["email", "roles", "branch_id"]

    def clean_roles(self) -> list[Role]:
        roles = self.cleaned_data.get("roles", [])
        if not roles:
            raise ValidationError("Select at least one role.")
        return roles


class AcceptInvitationForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            raise ValidationError("Passwords do not match.")
        return cleaned


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField()


class PasswordResetConfirmForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    new_password_confirm = forms.CharField(widget=forms.PasswordInput)

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("new_password") != cleaned.get("new_password_confirm"):
            raise ValidationError("Passwords do not match.")
        return cleaned


class AccountDashboardForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email"]
