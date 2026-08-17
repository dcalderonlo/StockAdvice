"""Demand override service and prompt helpers.

WU-13 allows branch managers to override the system-calculated expected demand
for a part. Three persistence modes are supported:

- Persistent: remains until manually changed.
- Per-run: applies to a single replenishment run only.
- With-expiry: remains until a specified date, then reverts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import structlog
from django.utils import timezone

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.branches.models import Branch
    from apps.catalog.models import DemandOverride, Part
    from apps.core.models import Tenant

logger = structlog.get_logger(__name__)


OVERRIDE_TYPE_DESCRIPTIONS = {
    "persistent": "Permanent override. Stays in effect until you manually change it.",
    "per_run": "One-time override. Applies only to the next replenishment run; subsequent runs use the calculated value.",
    "with_expiry": "Temporary override. Stays in effect until a date you specify, then reverts to the calculated value.",
}


def get_override_prompt_message() -> str:
    """Return the human-readable prompt explaining the 3 override options."""
    parts = [
        "You're overriding the system-calculated expected demand for this part.",
        "",
        "Please choose how long this override should apply:",
        "",
        "1. Persistent — " + OVERRIDE_TYPE_DESCRIPTIONS["persistent"],
        "2. Per-run — " + OVERRIDE_TYPE_DESCRIPTIONS["per_run"],
        "3. With expiry — " + OVERRIDE_TYPE_DESCRIPTIONS["with_expiry"],
        "",
        "Choose an option:",
    ]
    return "\n".join(parts)


class OverrideService:
    """Apply and query demand overrides for a tenant."""

    def __init__(self, tenant: "Tenant"):
        self.tenant = tenant

    def create_override(
        self,
        part: "Part",
        branch: Optional["Branch"],
        override_value: Decimal,
        override_type: str,
        user: "User",
        expires_at: Optional[date] = None,
        notes: str = "",
        run_id: Optional[str] = None,
    ) -> "DemandOverride":
        """Create or update a demand override.

        For PERSISTENT overrides, an existing persistent override for the same
        part/branch is updated in place so that only one persistent override
        exists per scope. For PER_RUN and WITH_EXPIRY, new records are created.
        """
        from apps.catalog.models import DemandOverride, DemandOverrideType

        if override_type not in DemandOverrideType.values:
            raise ValueError(f"Invalid override_type: {override_type}")

        if override_type == DemandOverrideType.WITH_EXPIRY and expires_at is None:
            raise ValueError("WITH_EXPIRY overrides require an expires_at date")

        if override_type == DemandOverrideType.PER_RUN and not run_id:
            raise ValueError("PER_RUN overrides require a run_id")

        if override_value < Decimal("0"):
            raise ValueError("override_value cannot be negative")

        if override_type == DemandOverrideType.PERSISTENT:
            existing = DemandOverride.objects.filter(
                tenant=self.tenant,
                part=part,
                branch=branch,
                override_type=DemandOverrideType.PERSISTENT,
            ).first()
            if existing:
                existing.override_value = override_value
                existing.created_by = user
                existing.created_at = timezone.now()
                existing.notes = notes
                existing.save()
                logger.info(
                    "demand_override.updated",
                    override_id=str(existing.id),
                    part_id=str(part.id),
                    branch_id=str(branch.id) if branch else None,
                    value=str(override_value),
                )
                return existing

        override = DemandOverride.objects.create(
            tenant=self.tenant,
            part=part,
            branch=branch,
            override_type=override_type,
            override_value=override_value,
            expires_at=expires_at,
            run_id=run_id or "",
            created_by=user,
            notes=notes,
        )
        logger.info(
            "demand_override.created",
            override_id=str(override.id),
            type=override_type,
            part_id=str(part.id),
            branch_id=str(branch.id) if branch else None,
            value=str(override_value),
        )

        from apps.notifications.triggers import notify_override_created

        notify_override_created(override)
        return override

    def get_active_override(
        self,
        part: "Part",
        branch: Optional["Branch"],
        run_date: Optional[date] = None,
        run_id: Optional[str] = None,
    ) -> Optional["DemandOverride"]:
        """Return the override to use for this part/branch/run.

        Priority:

        1. WITH_EXPIRY override that is still valid (expires_at >= run_date).
        2. PERSISTENT override.
        3. PER_RUN override matching ``run_id``.
        4. None.
        """
        from apps.catalog.models import DemandOverride, DemandOverrideType

        if run_date is None:
            run_date = timezone.now().date()

        candidates = DemandOverride.objects.filter(
            tenant=self.tenant,
            part=part,
            branch=branch,
        )

        # Priority 1: WITH_EXPIRY that is still valid.
        for ovr in candidates.filter(override_type=DemandOverrideType.WITH_EXPIRY):
            if ovr.expires_at and ovr.expires_at >= run_date:
                return ovr

        # Priority 2: PERSISTENT.
        persistent = candidates.filter(
            override_type=DemandOverrideType.PERSISTENT
        ).first()
        if persistent:
            return persistent

        # Priority 3: PER_RUN matching this run.
        if run_id:
            per_run = candidates.filter(
                override_type=DemandOverrideType.PER_RUN, run_id=run_id
            ).first()
            if per_run:
                return per_run

        return None

    def cleanup_expired_overrides(self) -> int:
        """Remove expired WITH_EXPIRY overrides and return the count deleted."""
        from apps.catalog.models import DemandOverride, DemandOverrideType

        today = timezone.now().date()
        expired = DemandOverride.objects.filter(
            tenant=self.tenant,
            override_type=DemandOverrideType.WITH_EXPIRY,
            expires_at__lt=today,
        )
        count = expired.count()

        from apps.notifications.triggers import notify_override_expired

        for expired_override in expired:
            notify_override_expired(expired_override)

        expired.delete()
        logger.info("demand_override.cleanup", deleted=count)
        return count
