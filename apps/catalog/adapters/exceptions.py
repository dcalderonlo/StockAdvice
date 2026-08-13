"""DMS adapter exception hierarchy.

Exceptions are split into retryable (transient) and non-retryable (permanent)
so the retry decorator can decide whether to attempt another call.
"""

from __future__ import annotations


class DMSError(Exception):
    """Base class for all DMS adapter errors."""


class DMSConnectionError(DMSError):
    """Transient error: the DMS could not be reached (network, DNS, refused)."""


class DMSTimeoutError(DMSError):
    """Transient error: the DMS did not respond within the configured timeout."""


class DMSUnavailableError(DMSError):
    """Transient error: the DMS returned an availability signal (e.g. HTTP 503)."""


class DMSAuthenticationError(DMSError):
    """Permanent error: credentials are invalid or expired and will not fix themselves."""


class DMSConfigurationError(DMSError):
    """Permanent error: the adapter configuration is missing or invalid."""


class DMSDataError(DMSError):
    """Permanent error: the DMS returned data that does not match the expected schema."""
