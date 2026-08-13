"""Management command to sync inventory from the DMS."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.branches.models import Branch
from apps.core.models import Tenant
from apps.inventory.services import InventoryIngestionService


class Command(BaseCommand):
    help = "Sync inventory data from the configured DMS adapter."

    def add_arguments(self, parser):
        parser.add_argument(
            "--branch",
            type=str,
            help="Sync a single branch by code (e.g. SUC-001).",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            help="Sync a single tenant by UUID slug or name.",
        )

    def handle(self, *args, **options):
        branch_code = options.get("branch")
        tenant_arg = options.get("tenant")

        tenants = self._resolve_tenants(tenant_arg)

        for tenant in tenants:
            service = InventoryIngestionService(tenant)

            if branch_code:
                try:
                    branch = Branch.objects.get(tenant=tenant, code=branch_code)
                except Branch.DoesNotExist:
                    raise CommandError(
                        f"Branch '{branch_code}' not found for tenant '{tenant}'."
                    )
                from datetime import date, timedelta

                service.sync_stock(branch.code)
                service.sync_sales(
                    branch.code, since_date=date.today() - timedelta(days=400)
                )
                service.sync_purchase_orders(branch.code)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Synced inventory for branch {branch.code} of tenant {tenant}."
                    )
                )
            else:
                results = service.run_full_sync()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Synced tenant {tenant}: {results['branches']} branches, "
                        f"{results['stock_levels']} stock levels, "
                        f"{results['movements']} movements."
                    )
                )

    def _resolve_tenants(self, tenant_arg: str | None):
        queryset = Tenant.objects.filter(is_active=True)
        if tenant_arg:
            tenant = queryset.filter(slug=tenant_arg).first()
            if not tenant:
                tenant = queryset.filter(name__iexact=tenant_arg).first()
            if not tenant:
                raise CommandError(f"Tenant '{tenant_arg}' not found.")
            return [tenant]
        return list(queryset)
