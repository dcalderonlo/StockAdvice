"""Notification type and channel enumerations."""

from __future__ import annotations

from django.db import models


class NotificationType(models.TextChoices):
    NEW_RECOMMENDATION = "new_recommendation", "New recommendation"
    RECOMMENDATION_ESCALATED = "recommendation_escalated", "Recommendation escalated"
    RECOMMENDATION_APPROVED = "recommendation_approved", "Recommendation approved"
    RECOMMENDATION_REJECTED = "recommendation_rejected", "Recommendation rejected"
    PARTIAL_FULFILLMENT = "partial_fulfillment", "Partial fulfillment detected"
    CROSS_COORDINATOR_PENDING = "cross_coordinator_pending", "Cross-coordinator transfer pending"
    OVERRIDE_CREATED = "override_created", "Demand override created"
    OVERRIDE_EXPIRED = "override_expired", "Demand override expired"


class NotificationChannel(models.TextChoices):
    EMAIL = "email", "Email"
    IN_APP = "in_app", "In-App"
