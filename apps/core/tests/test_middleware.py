from __future__ import annotations

import uuid

import pytest
from django.test import RequestFactory

from ..middleware import RequestContextMiddleware, TenantMiddleware
from .factories import TenantFactory


@pytest.fixture
def tenant_middleware() -> TenantMiddleware:
    return TenantMiddleware(lambda request: request)


@pytest.mark.django_db
class TestTenantMiddleware:
    def test_sets_request_tenant_from_header(self, tenant_middleware: TenantMiddleware) -> None:
        tenant = TenantFactory(slug="acme")
        request = RequestFactory().get("/", HTTP_X_TENANT_SLUG="acme")
        tenant_middleware(request)
        assert request.tenant == tenant

    def test_falls_back_to_default_tenant_in_dev(self, settings, tenant_middleware: TenantMiddleware) -> None:
        settings.DEBUG = True
        settings.DEFAULT_TENANT_SLUG = "default"
        request = RequestFactory().get("/")
        tenant_middleware(request)
        assert request.tenant is not None
        assert request.tenant.slug == "default"

    def test_returns_none_when_unknown_and_not_debug(self, settings, tenant_middleware: TenantMiddleware) -> None:
        settings.DEBUG = False
        request = RequestFactory().get("/", HTTP_X_TENANT_SLUG="missing")
        tenant_middleware(request)
        assert request.tenant is None


@pytest.fixture
def request_context_middleware() -> RequestContextMiddleware:
    return RequestContextMiddleware(lambda request: request)


@pytest.mark.django_db
class TestRequestContextMiddleware:
    def test_adds_request_id_to_anonymous_request(self, request_context_middleware: RequestContextMiddleware) -> None:
        request = RequestFactory().get("/")
        request_context_middleware.process_request(request)
        assert hasattr(request, "request_id")
        uuid.UUID(request.request_id)  # valid UUID
        assert request.log_extra["request_id"] == request.request_id
        assert request.log_extra["user_id"] is None
        assert request.log_extra["branch_id"] is None

    def test_adds_user_id_for_authenticated_user(self, request_context_middleware: RequestContextMiddleware) -> None:
        from apps.accounts.models import User

        user = User.objects.create(email="user@example.com")
        request = RequestFactory().get("/")
        request.user = user
        request_context_middleware.process_request(request)
        assert request.log_extra["user_id"] == str(user.id)

    def test_adds_branch_id_for_branch_manager(
        self, request_context_middleware: RequestContextMiddleware
    ) -> None:
        from apps.accounts.models import User
        from apps.branches.models import Branch, BranchType

        tenant = TenantFactory()
        user = User.objects.create(email="manager@example.com")
        branch = Branch.objects.create(
            tenant=tenant,
            code="SUC-001",
            name="Main Branch",
            type=BranchType.SUCURSAL,
            manager=user,
        )
        request = RequestFactory().get("/")
        request.user = user
        request_context_middleware.process_request(request)
        assert request.log_extra["user_id"] == str(user.id)
        assert request.log_extra["branch_id"] == str(branch.id)
