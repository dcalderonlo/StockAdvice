from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.sector.models import DEFAULT_CONFIG, DEFAULT_SECTOR_KEY, SectorConfiguration


class Command(BaseCommand):
    help = "Create the default automotive_aftermarket sector configuration."

    def handle(self, *args, **options):
        sector, created = SectorConfiguration.objects.get_or_create(
            sector_key=DEFAULT_SECTOR_KEY,
            defaults={
                "name": "Automotive Aftermarket",
                "description": "Default sector for automotive aftermarket parts (concesionarios).",
                "is_default": True,
                "config_json": DEFAULT_CONFIG,
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created default sector: {sector.sector_key}")
            )
        else:
            self.stdout.write(f"Default sector already exists: {sector.sector_key}")
