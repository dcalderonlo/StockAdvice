from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpRequest

from . import services
from .models import EmailVerification, Invitation, PasswordReset, Role, User, UserRole
from .permissions import has_conflict_of_interest


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_verified",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Tenant", {"fields": ("tenant",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    list_display = (
        "email",
        "tenant",
        "is_active",
        "is_verified",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "is_verified", "is_staff", "tenant")
    search_fields = ("email",)
    ordering = ("email",)
    inlines = [UserRoleInline]
    actions = ["disable_users"]

    def save_model(self, request: HttpRequest, obj: User, form, change) -> None:
        super().save_model(request, obj, form, change)
        if has_conflict_of_interest(obj):
            messages.warning(
                request,
                "Advertencia: este usuario tiene roles que pueden generar conflicto de intereses.",
            )

    @admin.action(description="Disable selected users")
    def disable_users(self, request: HttpRequest, queryset) -> None:
        queryset.update(is_active=False)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "branch_id")
    list_filter = ("role",)
    search_fields = ("user__email", "role__name")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "tenant", "status", "invited_by", "created_at")
    list_filter = ("status", "tenant")
    search_fields = ("email",)
    readonly_fields = ("token",)
    filter_horizontal = ("roles",)

    def save_model(self, request: HttpRequest, obj: Invitation, form, change) -> None:
        if not change:
            obj.invited_by = request.user
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)
        if not change:
            services.send_invitation_email(obj, request)
            messages.success(request, "Invitación enviada por correo.")

    def get_changeform_initial_data(self, request: HttpRequest) -> dict:
        return {"invited_by": request.user, "tenant": request.user.tenant}


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "verified_at")
    readonly_fields = ("token",)


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    readonly_fields = ("token",)
