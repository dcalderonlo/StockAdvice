"""Sector configuration model.

Stores sector-specific terminology, classification thresholds, lifecycle rules,
and behavioral flags. The system ships with a default ``automotive_aftermarket``
sector; other sectors can be added via the admin panel without code changes.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models


DEFAULT_SECTOR_KEY = "automotive_aftermarket"

DEFAULT_CONFIG: dict[str, Any] = {
    "terminology": {
        "part_label": "Part",
        "supplier_label": "Supplier",
        "warehouse_label": "Warehouse",
    },
    "classification": {
        "vc_thresholds": [
            {"min": 251, "label": "VC1"},
            {"min": 121, "label": "VC2"},
            {"min": 61, "label": "VC3"},
            {"min": 31, "label": "VC4"},
            {"min": 15, "label": "VC5"},
            {"min": 7, "label": "VC6"},
            {"min": 4, "label": "VC7"},
            {"min": 1, "label": "VC8"},
        ],
        "lifecycle_stages": [
            {"code": "NEW", "name": "New", "max_months": 6},
            {"code": "ACTIVE", "name": "Active"},
            {"code": "PRE_OBSOLETE", "name": "Pre-Obsolete", "min_months_no_sales": 12},
            {"code": "OBSOLETE", "name": "Obsolete", "min_months_no_sales": 24},
            {
                "code": "INACTIVE",
                "name": "Inactive",
                "min_months_no_sales": 12,
                "min_stock_zero": True,
            },
        ],
    },
    "notification_settings": {
        "email_enabled": True,
        "in_app_enabled": True,
    },
}


class SectorConfigurationManager(models.Manager):
    """Custom manager for sector configuration lookups."""

    def default(self) -> "SectorConfiguration | None":
        """Return the sector flagged as default, if one exists."""
        return self.filter(is_default=True).first()


class SectorConfiguration(models.Model):
    """A sector configuration: terminology, thresholds, and lifecycle rules."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sector_key = models.CharField(
        max_length=50,
        unique=True,
        help_text="Stable identifier, e.g. 'automotive_aftermarket'.",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(
        default=False,
        help_text="The default sector for new tenants. Only one sector should be default.",
    )
    config_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sector-specific configuration: terminology, classification thresholds, lifecycle rules.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SectorConfigurationManager()

    class Meta:
        ordering = ["sector_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["sector_key"], name="unique_sector_key"
            ),
        ]
        indexes = [
            models.Index(fields=["sector_key"]),
            models.Index(fields=["is_default"]),
        ]

    def __str__(self) -> str:
        return self.name

    def _vc_thresholds(self) -> list[dict[str, Any]]:
        """Return the configured VC thresholds, sorted highest ``min`` first."""
        classification = self.config_json.get("classification", {}) if isinstance(self.config_json, dict) else {}
        thresholds = classification.get("vc_thresholds", []) or []
        return sorted(thresholds, key=lambda t: t.get("min", 0), reverse=True)

    def get_vc_label(self, annual_sales: int) -> str:
        """Return the Volume Class label for the given annual sales count."""
        for threshold in self._vc_thresholds():
            if annual_sales >= threshold.get("min", 0):
                return threshold.get("label", "")
        return ""

    def _lifecycle_stages(self) -> list[dict[str, Any]]:
        """Return configured lifecycle stage definitions."""
        classification = self.config_json.get("classification", {}) if isinstance(self.config_json, dict) else {}
        return list(classification.get("lifecycle_stages", []) or [])

    def _stage_by_code(self, code: str) -> dict[str, Any] | None:
        """Return the lifecycle stage definition matching ``code``."""
        for stage in self._lifecycle_stages():
            if stage.get("code") == code:
                return stage
        return None

    def get_lifecycle_stage(
        self,
        months_since_first_seen: int | None = None,
        months_since_last_sale: int | None = None,
        has_stock: bool = False,
    ) -> str:
        """Return a lifecycle stage code based on age and sales history.

        Rules are inferred from the sector's lifecycle stage configuration:

        - ``max_months``      → new/introduction stage.
        - ``min_months_no_sales`` + ``min_stock_zero=True`` → inactive stage.
        - ``min_months_no_sales`` (largest value)            → obsolete stage.
        - ``min_months_no_sales`` (other values)             → pre-obsolete stage(s).
        - stage with no age/sales rules                      → active stage.
        """
        stages = self._lifecycle_stages()
        if not stages:
            return "ACTIVE"

        # Obsolete: stage with min_months_no_sales (largest value), no min_stock_zero.
        obsolete_candidates = [
            s
            for s in stages
            if s.get("min_months_no_sales") is not None and not s.get("min_stock_zero")
        ]
        if obsolete_candidates and months_since_last_sale is not None:
            obsolete = max(
                obsolete_candidates, key=lambda s: s.get("min_months_no_sales", 0)
            )
            if months_since_last_sale >= obsolete.get("min_months_no_sales", 0):
                return obsolete.get("code", "OBSOLETE")

        # Inactive: stage with min_stock_zero=True.
        inactive_candidates = [
            s for s in stages if s.get("min_months_no_sales") is not None and s.get("min_stock_zero")
        ]
        if inactive_candidates and months_since_last_sale is not None:
            inactive = max(
                inactive_candidates, key=lambda s: s.get("min_months_no_sales", 0)
            )
            if (
                months_since_last_sale >= inactive.get("min_months_no_sales", 0)
                and not has_stock
            ):
                return inactive.get("code", "INACTIVE")

        # Pre-obsolete: stage(s) with min_months_no_sales, not obsolete/inactive.
        pre_obs_candidates = [
            s
            for s in stages
            if s.get("min_months_no_sales") is not None and not s.get("min_stock_zero")
        ]
        if pre_obs_candidates and months_since_last_sale is not None and has_stock:
            for stage in sorted(
                pre_obs_candidates, key=lambda s: s.get("min_months_no_sales", 0)
            ):
                if months_since_last_sale >= stage.get("min_months_no_sales", 0):
                    return stage.get("code", "PRE_OBSOLETE")

        # New: stage with max_months.
        new_candidates = [s for s in stages if s.get("max_months") is not None]
        if new_candidates and months_since_first_seen is not None:
            new_stage = min(new_candidates, key=lambda s: s.get("max_months", 0))
            if months_since_first_seen <= new_stage.get("max_months", 0):
                return new_stage.get("code", "NEW")

        # Active: stage with no age/sales rules.
        active_candidates = [
            s
            for s in stages
            if s.get("max_months") is None and s.get("min_months_no_sales") is None
        ]
        if active_candidates:
            return active_candidates[0].get("code", "ACTIVE")

        return stages[0].get("code", "ACTIVE")
