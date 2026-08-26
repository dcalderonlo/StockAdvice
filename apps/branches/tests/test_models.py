"""Tests for the Branch model."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.tests.factories import TenantFactory

from ..models import Branch, BranchType


@pytest.fixture
def tenant():
    return TenantFactory()


@pytest.mark.django_db
def test_create_branch(tenant):
    branch = Branch.objects.create(
        tenant=tenant,
        code="SUC-001",
        name="Main Branch",
        type=BranchType.BRANCH,
    )
    assert branch.code == "SUC-001"
    assert branch.name == "Main Branch"
    assert branch.type == BranchType.BRANCH
    assert branch.is_active is True


@pytest.mark.django_db
def test_unique_code_per_tenant(tenant):
    Branch.objects.create(tenant=tenant, code="SUC-001", name="First", type=BranchType.BRANCH)
    with pytest.raises(Exception):
        Branch.objects.create(tenant=tenant, code="SUC-001", name="Second", type=BranchType.BRANCH)


@pytest.mark.django_db
def test_branch_type_helpers(tenant):
    dc = Branch.objects.create(
        tenant=tenant, code="CD-001", name="DC", type=BranchType.DISTRIBUTION_CENTER
    )
    suc = Branch.objects.create(
        tenant=tenant, code="SUC-001", name="Branch", type=BranchType.BRANCH
    )
    assert dc.is_distribution_center() is True
    assert dc.is_regular_branch() is False
    assert suc.is_distribution_center() is False
    assert suc.is_regular_branch() is True


@pytest.mark.django_db
def test_dc_cannot_have_parent(tenant):
    dc = Branch.objects.create(
        tenant=tenant, code="CD-001", name="DC", type=BranchType.DISTRIBUTION_CENTER
    )
    branch = Branch(
        tenant=tenant,
        code="SUC-001",
        name="Child",
        type=BranchType.DISTRIBUTION_CENTER,
        parent_branch=dc,
    )
    with pytest.raises(ValidationError):
        branch.full_clean()


@pytest.mark.django_db
def test_branch_can_have_parent_dc(tenant):
    dc = Branch.objects.create(
        tenant=tenant, code="CD-001", name="DC", type=BranchType.DISTRIBUTION_CENTER
    )
    branch = Branch.objects.create(
        tenant=tenant,
        code="SUC-001",
        name="Child",
        type=BranchType.BRANCH,
        parent_branch=dc,
    )
    assert branch.parent_branch == dc


@pytest.mark.django_db
def test_parent_must_be_dc(tenant):
    suc = Branch.objects.create(
        tenant=tenant, code="SUC-001", name="Branch", type=BranchType.BRANCH
    )
    child = Branch(
        tenant=tenant,
        code="SUC-002",
        name="Child",
        type=BranchType.BRANCH,
        parent_branch=suc,
    )
    with pytest.raises(ValidationError):
        child.full_clean()


@pytest.mark.django_db
def test_self_reference_not_allowed(tenant):
    branch = Branch(
        tenant=tenant,
        code="SUC-001",
        name="Branch",
        type=BranchType.BRANCH,
    )
    branch.save()
    branch.parent_branch = branch
    with pytest.raises(ValidationError):
        branch.full_clean()


@pytest.mark.django_db
def test_dependent_branches_relationship(tenant):
    dc = Branch.objects.create(
        tenant=tenant, code="CD-001", name="DC", type=BranchType.DISTRIBUTION_CENTER
    )
    b1 = Branch.objects.create(
        tenant=tenant,
        code="SUC-001",
        name="B1",
        type=BranchType.BRANCH,
        parent_branch=dc,
    )
    b2 = Branch.objects.create(
        tenant=tenant,
        code="SUC-002",
        name="B2",
        type=BranchType.BRANCH,
        parent_branch=dc,
    )
    dependents = list(dc.dependent_branches.all())
    assert len(dependents) == 2
    assert b1 in dependents
    assert b2 in dependents


@pytest.mark.django_db
def test_manager_and_coordinator_links(tenant):
    manager = User.objects.create(email="manager@example.com")
    coordinator = User.objects.create(email="coordinator@example.com")
    branch = Branch.objects.create(
        tenant=tenant,
        code="SUC-001",
        name="Branch",
        type=BranchType.BRANCH,
        manager=manager,
        coordinator=coordinator,
    )
    assert branch.manager == manager
    assert branch.coordinator == coordinator
    assert list(manager.managed_branches.all()) == [branch]
    assert list(coordinator.coordinated_branches.all()) == [branch]
