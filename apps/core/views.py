"""Core operational views: health checks and diagnostics."""

from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django_q.status import Stat


def health_check(request):
    """Return health status of web, db, and queue components.

    Returns HTTP 200 when all components are healthy, otherwise HTTP 503 with
    details about the failing component.
    """
    status = {"web": "ok", "db": "unknown", "queue": "unknown"}
    http_status = 200

    # Check DB
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        status["db"] = "ok"
    except Exception as e:
        status["db"] = f"error: {e}"
        http_status = 503

    # Check queue
    try:
        clusters = Stat.get_all()
        if clusters:
            status["queue"] = "ok"
        else:
            status["queue"] = "not running"
            http_status = 503
    except Exception as e:
        status["queue"] = f"error: {e}"
        http_status = 503

    return JsonResponse(status, status=http_status)
