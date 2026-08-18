from __future__ import annotations

from django.db import migrations, models
import uuid


DEFAULT_SECTOR_KEY = "automotive_aftermarket"

DEFAULT_CONFIG = {
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


def create_default_sector(apps, schema_editor):
    """Create the default automotive_aftermarket sector configuration."""
    SectorConfiguration = apps.get_model("sector", "SectorConfiguration")
    SectorConfiguration.objects.get_or_create(
        sector_key=DEFAULT_SECTOR_KEY,
        defaults={
            "name": "Automotive Aftermarket",
            "description": "Default sector for automotive aftermarket parts (concesionarios).",
            "is_default": True,
            "config_json": DEFAULT_CONFIG,
        },
    )


def remove_default_sector(apps, schema_editor):
    """Remove the default sector configuration on reversal."""
    SectorConfiguration = apps.get_model("sector", "SectorConfiguration")
    SectorConfiguration.objects.filter(sector_key=DEFAULT_SECTOR_KEY).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SectorConfiguration",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("sector_key", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("is_default", models.BooleanField(default=False)),
                ("config_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["sector_key"],
            },
        ),
        migrations.AddConstraint(
            model_name="sectorconfiguration",
            constraint=models.UniqueConstraint(
                fields=("sector_key",), name="unique_sector_key"
            ),
        ),
        migrations.AddIndex(
            model_name="sectorconfiguration",
            index=models.Index(fields=["sector_key"], name="sector_sector_key_idx"),
        ),
        migrations.AddIndex(
            model_name="sectorconfiguration",
            index=models.Index(fields=["is_default"], name="sector_is_default_idx"),
        ),
        migrations.RunPython(create_default_sector, remove_default_sector),
    ]
