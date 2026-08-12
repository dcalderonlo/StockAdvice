"""Tenant context for the current request / execution context."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Tenant

_current_tenant: ContextVar["Tenant | None"] = ContextVar("current_tenant", default=None)


def set_current_tenant(tenant: "Tenant | None") -> None:
    _current_tenant.set(tenant)


def get_current_tenant() -> "Tenant | None":
    return _current_tenant.get()
