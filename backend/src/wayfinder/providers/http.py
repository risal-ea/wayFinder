"""Shared async HTTP client for external data providers.

Everything every provider needs lives here, so provider clients only deal with
their own API shapes:

- a mandatory User-Agent and a request timeout
- retries with exponential backoff and jitter on timeouts, network errors,
  429, 5xx, empty bodies, invalid JSON and provider-specific "try again"
  payloads (e.g. MediaWiki `maxlag`)
- `Retry-After` honoured; waits longer than `max_retry_after` are not slept
  through but raised as `ProviderRateLimited` so the caller can report them
- limited concurrency (1 by default) and a minimum gap between requests;
  a backoff pauses *all* requests to that provider, not just the failed one
- one log line per call, with secrets such as `apikey` redacted
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from wayfinder.providers.errors import (
    ProviderRateLimited,
    ProviderRequestError,
    ProviderUnavailable,
)

logger = logging.getLogger("wayfinder.http")

Params = Mapping[str, str | int | float]
PayloadRetryCheck = Callable[[Any], bool]
Sleep = Callable[[float], Awaitable[None]]

REDACTED_PARAMS = frozenset({"apikey", "api_key", "key", "token", "access_token"})
_SECRET_IN_URL = re.compile(r"(?i)\b(apikey|api_key|access_token|token|key)=[^&\s\"']+")


def redact_url_secrets(text: str) -> str:
    return _SECRET_IN_URL.sub(r"\1=***", text)


class _RedactSecretsFilter(logging.Filter):
    """httpx logs every request URL at INFO; keys sent as query params would leak into logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact_url_secrets(message)
        if redacted != message:
            record.msg, record.args = redacted, ()
        return True


_httpx_logger = logging.getLogger("httpx")
if not any(isinstance(f, _RedactSecretsFilter) for f in _httpx_logger.filters):
    _httpx_logger.addFilter(_RedactSecretsFilter())


class _RetryableFailure(Exception):
    """One attempt failed in a way that is worth retrying."""

    def __init__(self, reason: str, *, retry_after: float | None = None, rate_limited: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after
        self.rate_limited = rate_limited


class ProviderHTTPClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        user_agent: str,
        timeout: float = 30.0,
        max_concurrency: int = 1,
        min_interval: float = 0.2,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
        rate_limit_wait: float = 5.0,
        max_retry_after: float = 60.0,
        default_params: Params | None = None,
        should_retry_payload: PayloadRetryCheck | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not user_agent.strip():
            raise ValueError(f"{provider}: a User-Agent is required")
        self.provider = provider
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self._default_params = {k: str(v) for k, v in (default_params or {}).items()}
        self._should_retry_payload = should_retry_payload
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._rate_limit_wait = rate_limit_wait
        self._max_retry_after = max_retry_after
        self._min_interval = min_interval
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._pacing_lock = asyncio.Lock()
        self._next_slot = 0.0  # time.monotonic() at which the next request may start

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> ProviderHTTPClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def get_json(self, path: str = "", params: Params | None = None) -> Any:
        """GET `path` and return the decoded JSON, retrying transient failures."""
        call_params = {k: str(v) for k, v in (params or {}).items()}
        merged = {**self._default_params, **call_params}
        started = time.monotonic()
        retries = 0

        while True:
            try:
                async with self._semaphore:
                    await self._wait_for_slot()
                    payload, status = await self._attempt(path, merged)
            except _RetryableFailure as failure:
                delay = self._retry_delay(failure, retries + 1)
                if retries >= self._max_retries or delay > self._max_retry_after:
                    self._log(path, call_params, f"failed: {failure.reason}", started, retries, logging.WARNING)
                    if failure.rate_limited or delay > self._max_retry_after:
                        raise ProviderRateLimited(self.provider, delay) from failure
                    raise ProviderUnavailable(
                        self.provider, f"{failure.reason} (after {retries} retries)"
                    ) from failure
                retries += 1
                logger.warning(
                    "%s GET %s %s: %s, retry %d/%d in %.1fs",
                    self.provider, path or "/", _describe(call_params),
                    failure.reason, retries, self._max_retries, delay,
                )
                self._pause(delay)
                continue
            except ProviderRequestError:
                self._log(path, call_params, "rejected", started, retries, logging.WARNING)
                raise

            self._log(path, call_params, f"status={status}", started, retries, logging.INFO)
            return payload

    async def _attempt(self, path: str, params: dict[str, str]) -> tuple[Any, int]:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise _RetryableFailure("timeout") from exc
        except httpx.TransportError as exc:
            raise _RetryableFailure(f"network error ({type(exc).__name__})") from exc

        status = response.status_code
        retry_after = parse_retry_after(response.headers.get("Retry-After"))

        if status == 429:
            raise _RetryableFailure("HTTP 429", retry_after=retry_after, rate_limited=True)
        if status >= 500:
            raise _RetryableFailure(f"HTTP {status}", retry_after=retry_after)
        if status >= 400:
            raise ProviderRequestError(self.provider, status, response.text)
        if not response.content.strip():
            raise _RetryableFailure("empty body")
        try:
            payload = response.json()
        except ValueError as exc:
            raise _RetryableFailure("invalid JSON") from exc
        if self._should_retry_payload is not None and self._should_retry_payload(payload):
            raise _RetryableFailure("provider asked to retry", retry_after=retry_after)
        return payload, status

    def _retry_delay(self, failure: _RetryableFailure, attempt: int) -> float:
        if failure.retry_after is not None:
            return failure.retry_after
        if failure.rate_limited:
            return self._rate_limit_wait
        backoff = min(self._backoff_max, self._backoff_base * 2 ** (attempt - 1))
        return backoff + random.uniform(0, self._backoff_base / 2)

    async def _wait_for_slot(self) -> None:
        async with self._pacing_lock:
            wait = self._next_slot - time.monotonic()
            if wait > 0:
                await self._sleep(wait)
            self._next_slot = max(time.monotonic(), self._next_slot) + self._min_interval

    def _pause(self, seconds: float) -> None:
        """Hold back every request to this provider for `seconds`."""
        self._next_slot = max(self._next_slot, time.monotonic() + seconds)

    def _log(self, path: str, params: dict[str, str], outcome: str, started: float, retries: int, level: int) -> None:
        logger.log(
            level,
            "%s GET %s %s %s duration_ms=%d retries=%d",
            self.provider, path or "/", _describe(params), outcome,
            (time.monotonic() - started) * 1000, retries,
        )


def parse_retry_after(value: str | None) -> float | None:
    """`Retry-After` is either a number of seconds or an HTTP date."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _describe(params: Mapping[str, str]) -> str:
    return " ".join(
        f"{k}={'***' if k.lower() in REDACTED_PARAMS else v}" for k, v in params.items()
    )
