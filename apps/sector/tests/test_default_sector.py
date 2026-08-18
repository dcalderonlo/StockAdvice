"""Tests for the create_default_sector management command."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.sector.models import SectorConfiguration


@pytest.mark.django_db
class TestCreateDefaultSectorCommand:
    def test_creates_default_sector(self):
        call_command("create_default_sector")
        sector = SectorConfiguration.objects.get(sector_key="automotive_aftermarket")
        assert sector.is_default is True
        assert sector.name == "Automotive Aftermarket"
        config = sector.config_json
        assert config["terminology"]["part_label"] == "Part"
        thresholds = config["classification"]["vc_thresholds"]
        assert thresholds[0]["label"] == "VC1"

    def test_idempotent(self):
        call_command("create_default_sector")
        call_command("create_default_sector")
        assert SectorConfiguration.objects.filter(sector_key="automotive_aftermarket").count() == 1
