"""Retry decorator for DMS adapter calls.

The decorator retries only a well-known set of transient exceptions. All other
exceptions are considered permanent and fail immediately. Configuration can be
overridden per tenant through ``Tenant.dms_config["retry"]``.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar

import structlog

from .exceptions import DMSConnectionError, DMSTimeoutError, DMSUnavailableError

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

RETRYABLE_EXCEPTIONS = (DMSConnectionError, DMSTimeoutError, DMSUnavailableError)


def _get_retry_config(instance: object | None) -> dict[str, Any]:
    """Extract the retry subsection from an adapter instance config."""
    if instance is None:
        return {}
    config = getattr(instance, "config", {}) or {}
    if not isinstance(config, dict):
        return {}
    retry_config = config.get("retry", {})
    return retry_config if isinstance(retry_config, dict) else {}


def _is_retry_enabled(instance: object | None) -> bool:
    """Return ``True`` unless the instance explicitly disables retries."""
    return _get_retry_config(instance).get("enabled", True)


def _delay_for_attempt(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate exponential backoff delay, capped at ``max_delay``."""
    return min(base_delay * (2 ** (attempt - 1)), max_delay)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    timeout_seconds: float = 30.0,
) -> Callable[[F], F]:
    """Retry a callable on transient DMS failures using exponential backoff.

    Default behaviour matches the design: 3 attempts, 1s/2s/4s delays,
    30s per-call timeout. Any of these values can be overridden per-tenant
    via ``adapter.config["retry"]``.

    The per-call timeout is stored in the adapter config so concrete DMS
    adapters can apply it to their own network/database requests. This
    decorator does not enforce the timeout itself because adapter calls may
    rely on connection-level timeouts or blocking IO that is best controlled
    by the implementation.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            instance = args[0] if args else None
            retry_config = _get_retry_config(instance)

            if not _is_retry_enabled(instance):
                return func(*args, **kwargs)

            attempts = int(retry_config.get("max_attempts", max_attempts))
            base = float(retry_config.get("base_delay_seconds", base_delay))
            maximum = float(retry_config.get("max_delay_seconds", max_delay))
            # Keep the configured timeout available for concrete adapters;
            # enforcement is left to the implementation's own request timeout.
            _ = float(retry_config.get("timeout_seconds", timeout_seconds))

            adapter_name = getattr(instance, "__class__", type(instance)).__name__
            method_name = func.__name__

            last_exception: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as exc:
                    last_exception = exc
                    if attempt == attempts:
                        logger.error(
                            "dms.retry.exhausted",
                            adapter=adapter_name,
                            method=method_name,
                            attempts=attempt,
                            error=str(exc),
                            error_type=type(exc).__name__,
                        )
                        raise
                    delay = _delay_for_attempt(attempt, base, maximum)
                    logger.warning(
                        "dms.retry.attempt",
                        adapter=adapter_name,
                        method=method_name,
                        attempt=attempt,
                        attempts=attempts,
                        delay=delay,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    time.sleep(delay)

            # pragma: no cover
            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
