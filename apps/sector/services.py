"""Sector configuration service layer."""

from __future__ import annotations

from typing import Any

from apps.core.models import Tenant

from .models import DEFAULT_SECTOR_KEY, SectorConfiguration


class SectorConfigurationService:
    """Resolve sector configuration and terminology for a tenant."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def get_sector(self) -> SectorConfiguration:
        """Return the tenant's sector configuration, defaulting to automotive."""
        config = self.tenant.config or {} if isinstance(self.tenant.config, dict) else {}
        sector_key = config.get("sector_key", DEFAULT_SECTOR_KEY)
        try:
            return SectorConfiguration.objects.get(sector_key=sector_key)
        except SectorConfiguration.DoesNotExist:
            default = SectorConfiguration.objects.default()
            if default is None:
                raise SectorConfiguration.DoesNotExist(
                    f"No sector configuration found for '{sector_key}' and no default is set."
                )
            return default

    def get_sector_for_tenant(self, tenant: Tenant | None = None) -> SectorConfiguration:
        """Return the sector configuration for the given tenant (or this service's tenant)."""
        target = tenant or self.tenant
        return self.__class__(target).get_sector()

    def get_terminology(self) -> dict[str, Any]:
        """Return terminology labels for the tenant's sector."""
        sector = self.get_sector()
        config = sector.config_json if isinstance(sector.config_json, dict) else {}
        return config.get("terminology", {}) or {}

    def get_vc_thresholds(self) -> list[dict[str, Any]]:
        """Return the Volume Class threshold list for the tenant's sector."""
        sector = self.get_sector()
        config = sector.config_json if isinstance(sector.config_json, dict) else {}
        classification = config.get("classification", {}) or {}
        return list(classification.get("vc_thresholds", []) or [])

    def get_lifecycle_stages(self) -> list[dict[str, Any]]:
        """Return the lifecycle stage definitions for the tenant's sector."""
        sector = self.get_sector()
        config = sector.config_json if isinstance(sector.config_json, dict) else {}
        classification = config.get("classification", {}) or {}
        return list(classification.get("lifecycle_stages", []) or [])
