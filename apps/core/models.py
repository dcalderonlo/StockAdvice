"""Core models: Tenant, AuditLog, and tenant-aware base class."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models
from django.utils.text import slugify

from .managers import TenantManager


class Tenant(models.Model):
    """A tenant (organization) that owns branches, users, and inventory data."""

    class Sector(models.TextChoices):
        AUTOMOTIVE = "automotive", "Automotive"
        PHARMACEUTICAL = "pharmaceutical", "Pharmaceutical"
        HARDWARE = "hardware", "Hardware"
        MANUFACTURING = "manufacturing", "Manufacturing"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    sector = models.CharField(
        max_length=50, choices=Sector.choices, default=Sector.AUTOMOTIVE
    )
    config = models.JSONField(default=dict, blank=True)
    dms_adapter_type = models.CharField(
        max_length=50,
        default="mock",
        help_text="Adapter identifier, e.g. 'mock', 'autologica', 'custom'.",
    )
    dms_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Adapter-specific configuration (connection string, credentials, etc.).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = slugify(self.name) or str(self.id)[:8]
        super().save(*args, **kwargs)


class TenantAwareModel(models.Model):
    """Abstract base class that links every row to a tenant."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
    )

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Immutable audit trail recording who did what and which role was used."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="audit_logs"
    )
    role_used = models.ForeignKey(
        "accounts.Role",
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} by {self.user} at {self.created_at}"
