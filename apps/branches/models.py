"""Branch model with distribution center topology."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TenantAwareModel

from .managers import BranchManager


class BranchType(models.TextChoices):
    SUCURSAL = "sucursal", "Sucursal"
    CENTRO_DISTRIBUCION = "centro_distribucion", "Centro de Distribución"


class Branch(TenantAwareModel):
    """A branch or distribution center belonging to a tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, help_text="Unique within the tenant, e.g. SUC-001 or CD-001")
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=BranchType.choices)
    parent_branch = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dependent_branches",
        help_text="For sucursales: the DC that supplies them. For DCs: null (top-level in v1).",
    )
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    manager = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_branches",
    )
    coordinator = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coordinated_branches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BranchManager()

    class Meta:
        ordering = ["tenant", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"], name="unique_branch_code_per_tenant"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def clean(self) -> None:
        super().clean()
        if self.type == BranchType.CENTRO_DISTRIBUCION and self.parent_branch is not None:
            raise ValidationError(
                {"parent_branch": "A distribution center cannot have a parent branch in v1."}
            )
        if self.parent_branch and self.parent_branch.type != BranchType.CENTRO_DISTRIBUCION:
            raise ValidationError(
                {"parent_branch": "A branch can only depend on a distribution center."}
            )
        if self.parent_branch and self.parent_branch_id == self.id:
            raise ValidationError(
                {"parent_branch": "A branch cannot be its own parent."}
            )

    def is_distribution_center(self) -> bool:
        return self.type == BranchType.CENTRO_DISTRIBUCION

    def is_regular_branch(self) -> bool:
        return self.type == BranchType.SUCURSAL
