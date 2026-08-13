"""Part catalog and cross-reference models."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TenantAwareModel


class Part(TenantAwareModel):
    """A part in the tenant's catalog."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    internal_sku_code = models.CharField(max_length=100)
    primary_manufacturer_code = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=500)
    category = models.CharField(max_length=100, blank=True)
    unit_of_measure = models.CharField(max_length=20, default="PCS")
    is_active = models.BooleanField(default=True)
    is_obsolete = models.BooleanField(default=False)
    lead_time_days = models.PositiveIntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant", "internal_sku_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "internal_sku_code"], name="unique_sku_per_tenant"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "primary_manufacturer_code"]),
            models.Index(fields=["tenant", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.internal_sku_code} - {self.description[:40]}"

    def alternative_manufacturer_codes(self) -> list[str]:
        """Return alternative manufacturer codes from cross-references."""
        return list(
            CrossReference.objects.filter(
                tenant=self.tenant,
                source_part=self,
                type=CrossReferenceType.ALTERNATIVE_MANUFACTURER,
                target_part__isnull=False,
            )
            .exclude(target_part__primary_manufacturer_code="")
            .values_list("target_part__primary_manufacturer_code", flat=True)
            .distinct()
        )


class CrossReferenceType(models.TextChoices):
    ALTERNATIVE_MANUFACTURER = "alternative_manufacturer", "Alternative Manufacturer"
    SAME_PART_ALTERNATIVE_CODE = "same_part_alternative_code", "Same Part Alternative Code"
    SUCCESSOR = "successor", "Successor"
    PREDECESSOR = "predecessor", "Predecessor"
    SUBSTITUTABLE = "substitutable", "Substitutable"


class CrossReference(TenantAwareModel):
    """A relationship between two parts or a part and an external code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_part = models.ForeignKey(
        Part,
        on_delete=models.CASCADE,
        related_name="outgoing_cross_references",
    )
    target_part = models.ForeignKey(
        Part,
        on_delete=models.CASCADE,
        related_name="incoming_cross_references",
        null=True,
        blank=True,
    )
    external_target_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="External code used when the target part is in another system.",
    )
    type = models.CharField(max_length=30, choices=CrossReferenceType.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tenant", "source_part", "type"]

    def __str__(self) -> str:
        target = self.target_part or self.external_target_code
        return f"{self.source_part} -> {self.target} ({self.type})"

    def clean(self) -> None:
        super().clean()
        if self.target_part is None and not self.external_target_code:
            raise ValidationError(
                "Cross-reference must point to either a target part or an external code."
            )
        if self.target_part is not None and self.external_target_code:
            raise ValidationError(
                "Provide either a target part or an external code, not both."
            )
        if self.target_part == self.source_part:
            raise ValidationError("A part cannot reference itself.")

    @property
    def target(self) -> str:
        return str(self.target_part) if self.target_part else self.external_target_code
