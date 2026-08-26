# Generated data migration: rename punto_pedido to reorder_point.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("recommendations", "0004_recommendation_escalated_at_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="recommendation",
            old_name="punto_pedido",
            new_name="reorder_point",
        ),
    ]
