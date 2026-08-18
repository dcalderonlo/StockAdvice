from __future__ import annotations

import pytest

from apps.accounts.models import Role
from apps.accounts.permissions import RoleNames


@pytest.fixture(autouse=True)
def seed_roles(db):
    for name in (
        RoleNames.ADMINISTRATOR,
        RoleNames.GERENTE,
        RoleNames.COORDINATOR,
        RoleNames.MANAGER,
    ):
        Role.objects.get_or_create(name=name)
