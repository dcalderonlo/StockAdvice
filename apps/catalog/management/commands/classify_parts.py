"""Management command to run the classification engine."""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.classification import ClassificationEngine
from apps.catalog.models import ClassificationResult, Part
from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Run the classification engine for parts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            help="Classify a single tenant by slug or name.",
        )
        parser.add_argument(
            "--part",
            type=str,
            help="Classify a single part by internal SKU code.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-classify even if the result is recent (within 24 hours).",
        )

    def handle(self, *args, **options):
        tenant_arg = options.get("tenant")
        part_sku = options.get("part")
        force = options.get("force", False)

        tenants = self._resolve_tenants(tenant_arg)

        total_classified = 0
        total_changed = 0
        skipped = 0

        for tenant in tenants:
            engine = ClassificationEngine(tenant)

            if part_sku:
                try:
                    part = Part.objects.get(tenant=tenant, internal_sku_code=part_sku)
                except Part.DoesNotExist:
                    raise CommandError(
                        f"Part '{part_sku}' not found for tenant '{tenant}'."
                    )
                previous = self._previous_result(part, tenant)
                if not force and self._is_recent(previous):
                    skipped += 1
                    self.stdout.write(
                        f"Skipped {part.internal_sku_code}: recently classified."
                    )
                    continue
                result = engine.classify_part(part)
                changed = self._status_changed(previous, result)
                total_classified += 1
                if changed:
                    total_changed += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Classified {part.internal_sku_code}: {result.lifecycle_stage} "
                        f"({result.volume_class or 'no VC'})."
                    )
                )
            else:
                parts = Part.objects.filter(tenant=tenant, is_active=True).order_by(
                    "id"
                )
                parts_to_classify = []
                for part in parts.iterator():
                    previous = self._previous_result(part, tenant)
                    if not force and self._is_recent(previous):
                        skipped += 1
                        continue
                    parts_to_classify.append((part, previous))

                for part, previous in parts_to_classify:
                    result = engine.classify_part(part)
                    total_classified += 1
                    if self._status_changed(previous, result):
                        total_changed += 1

        stale_note = " (forced)" if force else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Classified {total_classified} parts{stale_note}, "
                f"{total_changed} changed status, {skipped} skipped."
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

    def _previous_result(
        self, part: Part, tenant: Tenant
    ) -> ClassificationResult | None:
        return (
            ClassificationResult.objects.filter(
                tenant=tenant, part=part, classifier_version="1.0"
            )
            .order_by("-classified_at")
            .first()
        )

    def _is_recent(self, previous: ClassificationResult | None) -> bool:
        if previous is None:
            return False
        cutoff = timezone.now() - timedelta(hours=24)
        return previous.classified_at >= cutoff

    def _status_changed(
        self, previous: ClassificationResult | None, current: ClassificationResult
    ) -> bool:
        if previous is None:
            return True
        return (
            previous.lifecycle_stage != current.lifecycle_stage
            or previous.volume_class != current.volume_class
            or previous.lifecycle_subcode != current.lifecycle_subcode
        )
