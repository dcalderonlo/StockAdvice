"""Part catalog, cross-reference, and classification result models."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TenantAwareModel


class LifecycleStage(models.TextChoices):
    NEW = "new", "New"
    ACTIVE = "active", "Active"
    PRE_OBSOLETE = "pre_obsolete", "Pre-Obsolete"
    OBSOLETE = "obsolete", "Obsolete"
    INACTIVE = "inactive", "Inactive"
    SPECIAL_CAMPAIGN = "special_campaign", "Special (Campaign)"
    SPECIAL_NON_STOCK = "special_non_stock", "Special (Non-Stock)"


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
    special_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text='e.g., {"is_campaign": false, "is_non_stock": false, "campaign_notes": ""}',
    )
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


class ClassificationResultManager(models.Manager):
    """Manager helpers for querying classification snapshots."""

    def latest_for_part(
        self, part: "Part", branch=None, classifier_version: str = "1.0"
    ) -> "ClassificationResult | None":
        """Return the most recent classification result for a part/branch/version."""
        qs = self.filter(
            tenant=part.tenant,
            part=part,
            classifier_version=classifier_version,
        )
        if branch is not None:
            qs = qs.filter(branch=branch)
        else:
            qs = qs.filter(branch__isnull=True)
        return qs.order_by("-classified_at").first()

    def active_parts(self, tenant):
        """Return parts whose latest classification is not obsolete/inactive/non-stock."""
        return (
            self.filter(tenant=tenant)
            .exclude(
                lifecycle_stage__in=(
                    LifecycleStage.OBSOLETE,
                    LifecycleStage.INACTIVE,
                    LifecycleStage.SPECIAL_NON_STOCK,
                )
            )
            .values_list("part_id", flat=True)
            .distinct()
        )

    def stale(self, days: int = 35):
        """Return results older than ``days`` days (default: >1 month)."""
        from django.utils import timezone

        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(classified_at__lt=cutoff)


class ClassificationResult(TenantAwareModel):
    """A snapshot of the classification engine output for a part.

    The unique constraint on ``(tenant, part, branch, classifier_version)``
    allows history to be kept by bumping ``classifier_version`` in future
    migrations. For the current version the row is upserted on every pass.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    part = models.ForeignKey(
        Part,
        on_delete=models.CASCADE,
        related_name="classifications",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="classifications",
    )
    volume_class = models.CharField(
        max_length=4,
        blank=True,
        help_text="VC1..VC8 or empty for cold-start.",
    )
    lifecycle_stage = models.CharField(
        max_length=30,
        choices=LifecycleStage.choices,
    )
    lifecycle_subcode = models.CharField(
        max_length=10,
        blank=True,
        help_text="Granular code: N1/N2/N3 for new parts, OBS-P/OBS-R/etc. when applicable.",
    )
    annual_sales = models.PositiveIntegerField(default=0)
    days_since_last_sale = models.PositiveIntegerField(null=True, blank=True)
    months_since_first_seen = models.PositiveIntegerField(null=True, blank=True)
    classified_at = models.DateTimeField()
    classifier_version = models.CharField(max_length=10, default="1.0")
    special_flags = models.JSONField(default=dict, blank=True)

    objects = ClassificationResultManager()

    class Meta:
        ordering = ["-classified_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "part", "branch", "classifier_version"],
                name="unique_classification_per_version",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "part", "branch"]),
            models.Index(fields=["lifecycle_stage"]),
        ]

    def __str__(self) -> str:
        scope = f"@{self.branch.code}" if self.branch else "tenant-wide"
        return f"{self.part.internal_sku_code} {self.lifecycle_stage} {scope}"
