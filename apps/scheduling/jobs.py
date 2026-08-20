"""Background job definitions for the Django-Q2 scheduler."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import structlog
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.branches.models import Branch
from apps.catalog.classification import ClassificationEngine
from apps.catalog.overrides import OverrideService
from apps.core.models import Tenant
from apps.recommendations.services import RecommendationGenerator

from .models import ScheduledRun

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


def scheduled_replenishment_run(branch_id: str, run_date: str | None = None) -> int:
    """Run replenishment for a single branch. Idempotent by (branch_id, run_date)."""
    if run_date is None:
        run_date = timezone.now().date().isoformat()

    branch = Branch.objects.get(id=branch_id)
    tenant = branch.tenant

    existing = ScheduledRun.objects.filter(
        tenant=tenant,
        run_type="replenishment",
        branch=branch,
        run_date=run_date,
    ).first()
    if existing:
        logger.info(
            "replenishment_run.already_exists",
            branch=branch.code,
            run_date=run_date,
        )
        return existing.recommendations_count

    generator = RecommendationGenerator(tenant)
    recommendations = generator.generate_for_branch(
        branch, run_date=date.fromisoformat(run_date)
    )

    run = ScheduledRun.objects.create(
        tenant=tenant,
        run_type="replenishment",
        branch=branch,
        run_date=run_date,
        recommendations_count=len(recommendations),
        completed_at=timezone.now(),
    )
    logger.info(
        "replenishment_run.completed",
        branch=branch.code,
        run_date=run_date,
        count=run.recommendations_count,
    )
    return run.recommendations_count


def scheduled_classification_pass(tenant_id: str, month_key: str | None = None) -> int:
    """Run classification for all parts in a tenant. Idempotent by (tenant_id, month_key)."""
    if month_key is None:
        month_key = timezone.now().date().strftime("%Y-%m")

    tenant = Tenant.objects.get(id=tenant_id)

    existing = ScheduledRun.objects.filter(
        tenant=tenant,
        run_type="classification",
        run_date=month_key,
    ).first()
    if existing:
        logger.info(
            "classification_pass.already_exists",
            tenant=str(tenant.id),
            month_key=month_key,
        )
        return existing.recommendations_count

    engine = ClassificationEngine(tenant)
    results = engine.classify_tenant(tenant)

    run = ScheduledRun.objects.create(
        tenant=tenant,
        run_type="classification",
        run_date=month_key,
        recommendations_count=len(results),
        completed_at=timezone.now(),
    )
    logger.info(
        "classification_pass.completed",
        tenant=str(tenant.id),
        month_key=month_key,
        count=run.recommendations_count,
    )
    return run.recommendations_count


def scheduled_notification_dispatch() -> int:
    """Process pending email notifications (every 15 minutes)."""
    from apps.notifications.models import Notification

    pending = (
        Notification.objects.filter(
            sent_at__isnull=True,
            channel="email",
        )
        .select_related("user")
        .order_by("created_at")[:100]
    )

    sent_count = 0
    for notification in pending:
        try:
            send_mail(
                subject=notification.subject,
                message=notification.body,
                from_email=getattr(
                    settings, "DEFAULT_FROM_EMAIL", "noreply@stockadvice.local"
                ),
                recipient_list=[notification.user.email],
                fail_silently=False,
            )
            notification.sent_at = timezone.now()
            notification.save(update_fields=["sent_at", "updated_at"])
            sent_count += 1
            logger.info(
                "notification_dispatch.sent",
                notification_id=str(notification.id),
                user_id=str(notification.user_id),
            )
        except Exception as exc:  # noqa: BLE001
            notification.error = str(exc)
            notification.save(update_fields=["error", "updated_at"])
            logger.warning(
                "notification_dispatch.failed",
                notification_id=str(notification.id),
                error=str(exc),
            )

    return sent_count


def scheduled_override_cleanup() -> int:
    """Clean up expired WITH_EXPIRY demand overrides for all active tenants."""
    total = 0
    for tenant in Tenant.objects.filter(is_active=True):
        total += OverrideService(tenant).cleanup_expired_overrides()
    logger.info("override_cleanup.completed", deleted=total)
    return total
