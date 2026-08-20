"""Logging helpers that bridge structlog contextvars and stdlib logging."""

from __future__ import annotations

import logging

import structlog.contextvars


class StructlogContextFilter(logging.Filter):
    """Copy structlog contextvars into the stdlib LogRecord.

    This makes values bound by ``RequestContextMiddleware`` (request_id,
    user_id, branch_id) available to ``pythonjsonlogger.jsonlogger.JsonFormatter``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        context = structlog.contextvars.get_contextvars()
        for key in ("request_id", "user_id", "branch_id"):
            value = context.get(key)
            # JsonFormatter skips fields that are None; set empty string when
            # absent so the field is always present in structured output.
            setattr(record, key, value if value is not None else "")
        return True
