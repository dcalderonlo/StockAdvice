from __future__ import annotations

import pytest
from django.test import RequestFactory

from ..middleware import TenantMiddleware
from .factories import TenantFactory


@pytest.fixture
def middleware() -> TenantMiddleware:
    return TenantMiddleware(lambda request: request)


@pytest.mark.django_db
class TestTenantMiddleware:
    def test_sets_request_tenant_from_header(self, middleware: TenantMiddleware) -> None:
        tenant = TenantFactory(slug="acme")
        request = RequestFactory().get("/", HTTP_X_TENANT_SLUG="acme")
        middleware(request)
        assert request.tenant == tenant

    def test_falls_back_to_default_tenant_in_dev(self, settings, middleware: TenantMiddleware) -> None:
        settings.DEBUG = True
        settings.DEFAULT_TENANT_SLUG = "default"
        request = RequestFactory().get("/")
        middleware(request)
        assert request.tenant is not None
        assert request.tenant.slug == "default"

    def test_returns_none_when_unknown_and_not_debug(self, settings, middleware: TenantMiddleware) -> None:
        settings.DEBUG = False
        request = RequestFactory().get("/", HTTP_X_TENANT_SLUG="missing")
        middleware(request)
        assert request.tenant is None
