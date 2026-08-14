from __future__ import annotations

from django.db import models


class RecommendationState(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    HANDLED = "handled", "Handled"
    ORDERED = "ordered", "Ordered"
