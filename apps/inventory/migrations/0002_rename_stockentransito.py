# Generated data migration: rename StockEnTransito and stock level fields to English.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="StockEnTransito",
            new_name="InTransitStock",
        ),
        migrations.RenameField(
            model_name="stocklevel",
            old_name="stock_disponible",
            new_name="available_stock",
        ),
        migrations.RenameField(
            model_name="stocklevel",
            old_name="stock_en_transito",
            new_name="in_transit_stock",
        ),
        migrations.RenameIndex(
            model_name="intransitstock",
            old_name="inventory_s_tenant__138717_idx",
            new_name="inventory_i_tenant__b05537_idx",
        ),
        migrations.RenameIndex(
            model_name="intransitstock",
            old_name="inventory_s_tenant__868ba0_idx",
            new_name="inventory_i_tenant__2e095a_idx",
        ),
    ]
