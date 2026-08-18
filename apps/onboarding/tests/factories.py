from __future__ import annotations

import factory

from apps.core.tests.factories import TenantFactory

from ..models import OnboardingState


class OnboardingStateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OnboardingState
        django_get_or_create = ("tenant",)

    tenant = factory.SubFactory(TenantFactory)
    status = "not_started"
    dms_adapter_type = "mock"
    dms_config = factory.DictFactory
