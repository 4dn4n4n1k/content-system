"""Provider-independent exception hierarchy.

Stages catch ProviderError (usually converting it to a clean exit or a
per-shot failure); providers translate their SDK/HTTP errors into these so
no provider-specific exception type ever crosses a stage boundary.
"""


class ProviderError(Exception):
    """Base class for all provider failures."""

    def __init__(self, message: str, provider: str | None = None):
        self.provider = provider
        super().__init__(f"[{provider}] {message}" if provider else message)


class AuthenticationError(ProviderError):
    """Missing or rejected credentials. Retrying cannot help; fix .env."""


class PermanentFailure(ProviderError):
    """The request itself is bad (unknown model/voice/template, invalid
    params). Retrying the same request cannot succeed."""


class TemporaryFailure(ProviderError):
    """Transient upstream problem (network, 5xx, timeout). A retry may work."""


class RateLimitError(TemporaryFailure):
    """Provider throttled us. A delayed retry may work."""


def classify_http(status: int, body: str, provider: str) -> ProviderError:
    """Map an HTTP error response to the right exception type."""
    snippet = body[:300]
    if status in (401, 403):
        return AuthenticationError(f"HTTP {status}: {snippet}", provider)
    if status == 429:
        return RateLimitError(f"HTTP 429: {snippet}", provider)
    if status >= 500:
        return TemporaryFailure(f"HTTP {status}: {snippet}", provider)
    return PermanentFailure(f"HTTP {status}: {snippet}", provider)
