"""Thin email helper wrapping Django's mail backend."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
    from_email: str | None = None,
) -> int:
    """Render HTML + text templates and send a single email.

    Returns the number of successfully delivered messages (0 or 1).
    """
    from_address = from_email or getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@stockadvice.local"
    )
    text_body = render_to_string(f"emails/{template_name}.txt", context)
    html_body = render_to_string(f"emails/{template_name}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_address,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    return message.send()
