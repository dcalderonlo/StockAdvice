"""Middleware that resolves and attaches the current tenant to every request."""

from __future__ import annotations

from typing import Callable

import structlog
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .context import set_current_tenant
from .models import Tenant

logger = structlog.get_logger(__name__)


class TenantMiddleware:
    """Resolve tenant from header/query/session and set ``request.tenant``."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tenant = self.resolve_tenant(request)
        request.tenant = tenant
        set_current_tenant(tenant)
        response = self.get_response(request)
        set_current_tenant(None)
        return response

    def resolve_tenant(self, request: HttpRequest) -> Tenant | None:
        session = getattr(request, "session", {})
        slug = (
            request.headers.get("X-Tenant-Slug")
            or request.GET.get("tenant")
            or session.get("tenant_slug")
        )
        if slug:
            try:
                return Tenant.objects.active().get(slug=slug)
            except Tenant.DoesNotExist:
                logger.warning("tenant_not_found", slug=slug)

        if getattr(settings, "DEBUG", False):
            default_slug = getattr(settings, "DEFAULT_TENANT_SLUG", "default")
            tenant, _ = Tenant.objects.get_or_create(
                slug=default_slug,
                defaults={
                    "name": "Default Tenant",
                    "sector": Tenant.Sector.AUTOMOTIVE,
                },
            )
            return tenant

        return None
