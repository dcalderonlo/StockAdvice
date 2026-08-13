"""Custom managers for the Branch model."""

from __future__ import annotations

from django.db import models


class BranchQuerySet(models.QuerySet):
    def active(self) -> "BranchQuerySet":
        return self.filter(is_active=True)

    def distribution_centers(self) -> "BranchQuerySet":
        return self.filter(type="centro_distribucion")

    def regular(self) -> "BranchQuerySet":
        return self.filter(type="sucursal")


class BranchManager(models.Manager):
    """Manager for ``Branch`` with topology helpers."""

    def get_queryset(self) -> BranchQuerySet:
        return BranchQuerySet(self.model, using=self._db)

    def active(self) -> BranchQuerySet:
        return self.get_queryset().active()

    def distribution_centers(self) -> BranchQuerySet:
        return self.get_queryset().distribution_centers()

    def regular(self) -> BranchQuerySet:
        return self.get_queryset().regular()
