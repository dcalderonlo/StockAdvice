# Generated data migration: update default sector description to English.

from django.db import migrations


def forwards(apps, schema_editor):
    SectorConfiguration = apps.get_model("sector", "SectorConfiguration")
    SectorConfiguration.objects.filter(sector_key="automotive_aftermarket").update(
        description="Default sector for automotive aftermarket parts (dealerships).",
    )


def reverse(apps, schema_editor):
    SectorConfiguration = apps.get_model("sector", "SectorConfiguration")
    SectorConfiguration.objects.filter(sector_key="automotive_aftermarket").update(
        description="Default sector for automotive aftermarket parts (concesionarios).",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sector", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(code=forwards, reverse_code=reverse),
    ]
