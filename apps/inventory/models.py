"""Inventory models: stock levels, movements, and in-transit records."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.branches.models import Branch
from apps.catalog.models import Part
from apps.core.models import TenantAwareModel


class StockLevel(TenantAwareModel):
    """Current stock position for a part at a branch."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="stock_levels"
    )
    part = models.ForeignKey(
        Part, on_delete=models.CASCADE, related_name="stock_levels"
    )
    stock_disponible = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    stock_en_transito = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["branch", "part__internal_sku_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "branch", "part"],
                name="unique_stock_per_tenant_branch_part",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "branch", "part"]),
            models.Index(fields=["last_synced_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.branch.code} / {self.part.internal_sku_code}"

    @property
    def total_stock(self) -> Decimal:
        return self.stock_disponible + self.stock_en_transito

    def clean(self) -> None:
        super().clean()
        if self.stock_disponible < 0:
            raise ValidationError(
                {"stock_disponible": "Stock disponible cannot be negative."}
            )
        if self.stock_en_transito < 0:
            raise ValidationError(
                {"stock_en_transito": "Stock en tránsito cannot be negative."}
            )


class StockMovementType(models.TextChoices):
    SALE = "sale", "Sale"
    PURCHASE = "purchase", "Purchase"
    TRANSFER_OUT = "transfer_out", "Transfer Out"
    TRANSFER_IN = "transfer_in", "Transfer In"
    ADJUSTMENT = "adjustment", "Adjustment"
    RETURN = "return", "Return"


class StockMovement(TenantAwareModel):
    """A signed movement of stock for a part at a branch."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="movements"
    )
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=StockMovementType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    movement_date = models.DateField()
    source = models.CharField(max_length=50, default="dms")
    external_reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-movement_date", "branch", "part"]
        indexes = [
            models.Index(fields=["tenant", "branch", "part", "movement_date"]),
            models.Index(fields=["movement_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.quantity} @ {self.branch.code}"

    def is_outflow(self) -> bool:
        return self.quantity < 0 or self.movement_type in (
            StockMovementType.SALE,
            StockMovementType.TRANSFER_OUT,
        )

    def is_inflow(self) -> bool:
        return self.quantity > 0 or self.movement_type in (
            StockMovementType.PURCHASE,
            StockMovementType.TRANSFER_IN,
            StockMovementType.RETURN,
        )


class StockEnTransitoStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_TRANSIT = "in_transit", "In Transit"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class StockEnTransito(TenantAwareModel):
    """System-initiated inter-branch transfer that is currently in transit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="outgoing_transfers",
    )
    destination_branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="incoming_transfers",
    )
    part = models.ForeignKey(
        Part, on_delete=models.CASCADE, related_name="in_transit_records"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=StockEnTransitoStatus.choices,
        default=StockEnTransitoStatus.PENDING,
    )
    expected_arrival = models.DateField()
    actual_arrival = models.DateField(null=True, blank=True)
    external_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Recommendation ID or other external reference that initiated the transfer.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expected_arrival", "destination_branch", "part"]
        indexes = [
            models.Index(fields=["tenant", "destination_branch", "status"]),
            models.Index(fields=["tenant", "source_branch", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.source_branch.code} -> {self.destination_branch.code}: {self.part.internal_sku_code}"

    def clean(self) -> None:
        super().clean()
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be positive."})
        if self.source_branch_id == self.destination_branch_id:
            raise ValidationError(
                {"destination_branch": "Source and destination branches must differ."}
            )

    @transaction.atomic
    def mark_received(self, quantity: Decimal | None = None) -> None:
        """Mark this transfer as received and update the destination StockLevel."""
        if self.status == StockEnTransitoStatus.RECEIVED:
            return

        if self.status == StockEnTransitoStatus.CANCELLED:
            raise ValidationError("Cannot mark a cancelled transfer as received.")

        received_quantity = quantity if quantity is not None else self.quantity
        if received_quantity <= 0:
            raise ValidationError({"quantity": "Received quantity must be positive."})

        stock_level, _ = StockLevel.objects.get_or_create(
            tenant=self.tenant,
            branch=self.destination_branch,
            part=self.part,
            defaults={
                "stock_disponible": Decimal("0"),
                "stock_en_transito": Decimal("0"),
            },
        )

        # Remove from transit and add to available stock at destination.
        stock_level.stock_en_transito = max(
            Decimal("0"), stock_level.stock_en_transito - self.quantity
        )
        stock_level.stock_disponible += received_quantity
        stock_level.last_synced_at = timezone.now()
        stock_level.save()

        self.actual_arrival = timezone.now().date()
        self.status = StockEnTransitoStatus.RECEIVED
        self.save()
