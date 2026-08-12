"""Lightweight account views for StockAdvice."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return HttpResponse(f"Logged in as {request.user.email}")
