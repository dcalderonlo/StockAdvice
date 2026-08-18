from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import Role, User, UserRole
from apps.core.tests.factories import TenantFactory


pytestmark = pytest.mark.django_db


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.fixture
def admin_user(tenant):
    user = User.objects.create_user(
        email="admin@example.com", password="password", tenant=tenant
    )
    admin_role = Role.objects.get(name=Role.ADMINISTRATOR)
    UserRole.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def plain_user(tenant):
    user = User.objects.create_user(
        email="plain@example.com", password="password", tenant=tenant
    )
    return user


class TestOnboardingStatusView:
    def test_status_view_requires_login(self, client):
        response = client.get(reverse("onboarding:status"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_status_view_renders_for_authenticated_user(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get(reverse("onboarding:status"))
        assert response.status_code == 200
        assert "Onboarding" in response.content.decode()

    def test_status_view_rejects_user_without_tenant(self, client, plain_user):
        client.force_login(plain_user)
        response = client.get(reverse("onboarding:status"))
        assert response.status_code == 403


class TestOnboardingActionViews:
    def test_test_dms_requires_login(self, client):
        response = client.post(reverse("onboarding:test-dms"))
        assert response.status_code == 302

    def test_test_dms_redirects_after_post(self, client, admin_user):
        client.force_login(admin_user)
        response = client.post(reverse("onboarding:test-dms"))
        assert response.status_code == 302
        assert response.url == reverse("onboarding:status")

    def test_backfill_redirects_after_post(self, client, admin_user):
        client.force_login(admin_user)
        response = client.post(reverse("onboarding:backfill"))
        assert response.status_code == 302
        assert response.url == reverse("onboarding:status")

    def test_test_run_redirects_after_post(self, client, admin_user):
        client.force_login(admin_user)
        response = client.post(reverse("onboarding:test-run"))
        assert response.status_code == 302
        assert response.url == reverse("onboarding:status")
