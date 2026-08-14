"""Custom model managers for tenant-aware queries."""

from __future__ import annotations

from uuid import UUID

from django.db import models


class TenantQuerySet(models.QuerySet):
    def active(self) -> "TenantQuerySet":
        return self.filter(is_active=True)


class TenantManager(models.Manager):
    """Manager for ``Tenant`` with an ``active()`` filter."""

    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)

    def active(self) -> TenantQuerySet:
        return self.get_queryset().active()


class TenantAwareManager(models.Manager):
    """Future manager for tenant-scoped models (placeholder for WU-02+)."""

    def for_tenant(self, tenant_id: str) -> models.QuerySet:
        return self.get_queryset().filter(tenant_id=tenant_id)


class AuditLogManager(models.Manager):
    """Manager for ``AuditLog`` with entity-scoped lookups."""

    def for_entity(self, entity_type: str, entity_id: UUID) -> models.QuerySet:
        return self.get_queryset().filter(
            entity_type=entity_type, entity_id=entity_id
        )
