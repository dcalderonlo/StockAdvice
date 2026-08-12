"""Core models: Tenant and tenant-aware base class."""

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
