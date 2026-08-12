from __future__ import annotations

import pytest

from ..models import Tenant
from .factories import TenantFactory


@pytest.mark.django_db
class TestTenant:
    def test_create_tenant(self) -> None:
        tenant = TenantFactory(name="Acme Automotive")
        assert tenant.name == "Acme Automotive"
        assert tenant.is_active is True

    def test_active_manager(self) -> None:
        active = TenantFactory(is_active=True)
        TenantFactory(is_active=False)
        assert Tenant.objects.active().count() == 1
        assert Tenant.objects.active().first() == active

    def test_str(self) -> None:
        tenant = TenantFactory(name="Acme")
        assert str(tenant) == "Acme"

    def test_slug_auto_generated(self) -> None:
        tenant = Tenant(name="Acme Automotive")
        tenant.save()
        assert tenant.slug == "acme-automotive"
