"""Management command to run the full onboarding flow for a tenant."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.core.models import Tenant

from apps.onboarding.services import OnboardingService


class Command(BaseCommand):
    help = "Run the full onboarding flow for a tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True)
        parser.add_argument("--dms-adapter", default="mock")
        parser.add_argument("--dms-config", default="{}", type=json.loads)
        parser.add_argument("--auto-go-live", action="store_true")

    def handle(self, *args, **options):
        tenant = Tenant.objects.get(slug=options["tenant_slug"])
        service = OnboardingService(tenant)

        # 1. Start onboarding
        service.start_onboarding(options["dms_adapter"], options["dms_config"])
        self.stdout.write("1. Onboarding started")

        # 2. Test DMS
        if service.test_dms_connection():
            self.stdout.write("2. DMS connection OK")
        else:
            self.stdout.write("2. DMS connection FAILED")
            return

        # 3. Backfill sales
        count = service.backfill_sales()
        self.stdout.write(f"3. Backfilled {count} sales records")

        # 4. Test run
        if options["auto_go_live"]:
            rec_count = service.run_test_recommendation()
            self.stdout.write(
                f"4. Test run: {rec_count} recommendations, GO LIVE"
            )
        else:
            self.stdout.write("4. Test run not executed (--auto-go-live not set)")
