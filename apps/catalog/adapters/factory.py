"""Factory for resolving a tenant's DMS adapter."""

from __future__ import annotations

from apps.core.models import Tenant

from .base import BaseDMSAdapter
from .mock import MockDMSAdapter


def _resolve_adapter(adapter_type: str, config: dict) -> BaseDMSAdapter:
    """Instantiate an adapter from ``adapter_type`` and ``config``."""
    if adapter_type == "mock":
        return MockDMSAdapter(config)

    if adapter_type == "autologica":
        # Real DMS adapter implementations are intentionally deferred until
        # the first concrete tenant integration.
        raise NotImplementedError("Autologica adapter is not yet implemented")

    raise ValueError(f"Unknown DMS adapter type: {adapter_type}")


def get_dms_adapter(tenant: Tenant) -> BaseDMSAdapter:
    """Return the DMS adapter configured for ``tenant``.

    The adapter type is read from ``tenant.dms_adapter_type`` and the adapter
    is initialized with ``tenant.dms_config``. Unknown adapter types raise
    ``ValueError``; adapters that are planned but not implemented raise
    ``NotImplementedError``.
    """
    adapter_type = tenant.dms_adapter_type or "mock"
    config = tenant.dms_config or {}
    return _resolve_adapter(adapter_type, config)


def get_dms_adapter_for_tenant(
    tenant: Tenant, adapter_type: str | None, config: dict | None
) -> BaseDMSAdapter:
    """Return a DMS adapter using explicit type/config.

    Used during onboarding before the tenant's DMS settings are committed.
    Falls back to the tenant's configured adapter when no explicit type is
    provided.
    """
    adapter_type = adapter_type or tenant.dms_adapter_type or "mock"
    config = config if config is not None else tenant.dms_config or {}
    return _resolve_adapter(adapter_type, config)
