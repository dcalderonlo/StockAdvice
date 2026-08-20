from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from ..views import health_check


@pytest.mark.django_db
class TestHealthCheck:
    def _parse(self, response):
        return json.loads(response.content.decode("utf-8"))

    def test_returns_200_when_all_healthy(self) -> None:
        with patch("apps.core.views.Stat.get_all", return_value=[object()]):
            request = RequestFactory().get("/health/")
            response = health_check(request)

        assert response.status_code == 200
        data = self._parse(response)
        assert data["web"] == "ok"
        assert data["db"] == "ok"
        assert data["queue"] == "ok"

    def test_returns_503_when_db_fails(self) -> None:
        with patch("apps.core.views.connection") as mock_connection:
            mock_connection.ensure_connection.side_effect = Exception("db down")
            request = RequestFactory().get("/health/")
            response = health_check(request)

        assert response.status_code == 503
        data = self._parse(response)
        assert data["web"] == "ok"
        assert "db down" in data["db"]

    def test_returns_503_when_queue_not_running(self) -> None:
        with patch("apps.core.views.Stat.get_all", return_value=[]):
            request = RequestFactory().get("/health/")
            response = health_check(request)

        assert response.status_code == 503
        data = self._parse(response)
        assert data["queue"] == "not running"

    def test_returns_503_when_queue_check_raises(self) -> None:
        with patch("apps.core.views.Stat.get_all", side_effect=Exception("queue unreachable")):
            request = RequestFactory().get("/health/")
            response = health_check(request)

        assert response.status_code == 503
        data = self._parse(response)
        assert "queue unreachable" in data["queue"]
