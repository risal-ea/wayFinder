"""Errors raised by provider clients.

Callers (services, MCP tools) catch these and turn them into short structured
messages; they never need to know about httpx.
"""


class ProviderError(Exception):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider


class ProviderUnavailable(ProviderError):
    """Retries exhausted on timeouts, 5xx, empty or invalid responses."""


class ProviderRateLimited(ProviderError):
    """The provider asked us to slow down for longer than we are willing to wait."""

    def __init__(self, provider: str, retry_after: float) -> None:
        super().__init__(provider, f"rate limited, retry in {retry_after:.0f}s")
        self.retry_after = retry_after


class ProviderRequestError(ProviderError):
    """A non-retryable HTTP error (4xx other than 429), e.g. a 403 for a bad User-Agent."""

    def __init__(self, provider: str, status: int, body: str) -> None:
        super().__init__(provider, f"HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body
