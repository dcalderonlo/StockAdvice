"""Management command to install default Django-Q2 schedules."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.models import Tenant

from ...schedules import setup_default_schedules


class Command(BaseCommand):
    help = "Set up default recurring schedules for all tenants."

    def handle(self, *args: object, **options: object) -> None:
        for tenant in Tenant.objects.filter(is_active=True):
            setup_default_schedules(tenant)
            self.stdout.write(
                self.style.SUCCESS(f"Schedules set up for tenant: {tenant.slug}")
            )
