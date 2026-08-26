"""Data migration: rename Role 'gerente' to 'department_manager'.

This translates the stored Role.name value 'gerente' (Spanish) to the new
value 'department_manager' (English). The Python constant Role.GERENTE
was also updated to 'department_manager' in apps/accounts/models.py, so
this migration ensures existing database rows are in sync with the new
constant.

Reversible so that rolling back the role slug translation is also possible.
"""

from django.db import migrations


def rename_gerente_to_department_manager(apps, schema_editor):
    """Translate Role.name 'gerente' -> 'department_manager'."""
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(name="gerente").update(name="department_manager")


def rename_department_manager_to_gerente(apps, schema_editor):
    """Reverse translation: 'department_manager' -> 'gerente'."""
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(name="department_manager").update(name="gerente")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_is_verified_emailverification_invitation_and_more"),
    ]

    operations = [
        migrations.RunPython(
            code=rename_gerente_to_department_manager,
            reverse_code=rename_department_manager_to_gerente,
        ),
    ]
