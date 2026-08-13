"""Django admin configuration for the catalog."""

from __future__ import annotations

import csv
import io
from typing import Any

from django.contrib import admin, messages
from django.http import HttpRequest

from .models import CrossReference, Part


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = (
        "internal_sku_code",
        "description",
        "primary_manufacturer_code",
        "category",
        "is_active",
    )
    list_filter = ("is_active", "is_obsolete", "category")
    search_fields = ("internal_sku_code", "primary_manufacturer_code", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["upload_csv"]

    @admin.action(description="Upload parts catalog from CSV")
    def upload_csv(self, request: HttpRequest, queryset: Any) -> None:
        """Placeholder action: real upload is handled by a custom admin view."""
        messages.info(
            request,
            "CSV upload is available through the custom upload view in the catalog menu.",
        )


@admin.register(CrossReference)
class CrossReferenceAdmin(admin.ModelAdmin):
    list_display = ("source_part", "target", "type", "tenant")
    list_filter = ("type", "tenant")
    search_fields = (
        "source_part__internal_sku_code",
        "target_part__internal_sku_code",
        "external_target_code",
    )
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("source_part", "target_part")


def _import_parts_from_csv(tenant: Any, reader: csv.DictReader) -> tuple[int, int]:
    """Import or update parts from a CSV reader.

    Required columns: internal_sku_code, description.
    Optional columns: primary_manufacturer_code, category, unit_of_measure,
    lead_time_days, is_active, is_obsolete.
    """
    created = 0
    updated = 0
    for row in reader:
        sku = row["internal_sku_code"].strip()
        defaults = {
            "description": row.get("description", "").strip(),
            "primary_manufacturer_code": row.get("primary_manufacturer_code", "").strip(),
            "category": row.get("category", "").strip(),
            "unit_of_measure": row.get("unit_of_measure", "PCS").strip() or "PCS",
        }
        if "lead_time_days" in row and row["lead_time_days"].strip():
            defaults["lead_time_days"] = int(row["lead_time_days"])
        if "is_active" in row:
            defaults["is_active"] = row["is_active"].strip().lower() in ("true", "1", "yes")
        if "is_obsolete" in row:
            defaults["is_obsolete"] = row["is_obsolete"].strip().lower() in ("true", "1", "yes")

        part, was_created = Part.objects.update_or_create(
            tenant=tenant,
            internal_sku_code=sku,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


class CatalogCSVImportService:
    """Service for importing parts from a CSV file."""

    REQUIRED_COLUMNS = {"internal_sku_code", "description"}

    @classmethod
    def import_csv(cls, tenant: Any, csv_file: Any) -> dict[str, int]:
        """Import parts from an uploaded CSV file."""
        content = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")
        missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        created, updated = _import_parts_from_csv(tenant, reader)
        return {"created": created, "updated": updated}
