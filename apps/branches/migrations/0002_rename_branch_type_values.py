# Generated data migration: map legacy Spanish branch type values to English.

from django.db import migrations, models


def forwards(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    Branch.objects.filter(type="sucursal").update(type="branch")
    Branch.objects.filter(type="centro_distribucion").update(type="distribution_center")


def reverse(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    Branch.objects.filter(type="branch").update(type="sucursal")
    Branch.objects.filter(type="distribution_center").update(type="centro_distribucion")


class Migration(migrations.Migration):
    dependencies = [
        ("branches", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="branch",
            name="type",
            field=models.CharField(
                choices=[
                    ("branch", "Branch"),
                    ("distribution_center", "Distribution Center"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(code=forwards, reverse_code=reverse),
    ]
