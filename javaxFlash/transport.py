from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Any

import requests

from .config import FlashConfig
from .errors import ProviderError, RetryExhaustedError, TimeoutError


@dataclass(slots=True)
class TransportResult:
    payload: Any
    status_code: int
    retry_count: int
    latency_ms: float


class HttpTransport:
    def __init__(
        self,
        config: FlashConfig,
        *,
        session: requests.Session | None = None,
        sleeper=time.sleep,
        random_fn=random.uniform,
    ):
        self.config = config
        self.session = session or requests.Session()
        self.sleeper = sleeper
        self.random_fn = random_fn

    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        provider_name: str,
    ) -> TransportResult:
        attempts = 0
        last_error: ProviderError | None = None

        while True:
            started_at = time.perf_counter()
            try:
                self._log(f"[{provider_name}] POST {url} json={payload}")
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=self.config.timeout,
                )
                latency_ms = (time.perf_counter() - started_at) * 1000

                if response.status_code in self.config.retry_status_codes:
                    error = self._http_error(
                        provider_name=provider_name,
                        response=response,
                        retryable=True,
                    )
                    raise error

                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    raise self._http_error(
                        provider_name=provider_name,
                        response=response,
                        retryable=False,
                    ) from exc

                try:
                    data = response.json()
                except ValueError as exc:
                    raise ProviderError(
                        f"{provider_name} returned invalid JSON",
                        provider=provider_name,
                        status_code=response.status_code,
                    ) from exc

                return TransportResult(
                    payload=data,
                    status_code=response.status_code,
                    retry_count=attempts,
                    latency_ms=latency_ms,
                )

            except requests.Timeout as exc:
                last_error = TimeoutError(
                    f"{provider_name} request timed out after {self.config.timeout}s",
                    provider=provider_name,
                )
            except requests.ConnectionError as exc:
                last_error = ProviderError(
                    f"{provider_name} temporary network failure: {exc}",
                    provider=provider_name,
                )
            except ProviderError as exc:
                last_error = exc
            except requests.RequestException as exc:
                last_error = ProviderError(
                    f"{provider_name} request failed: {exc}",
                    provider=provider_name,
                )

            if last_error is None:
                raise RuntimeError("transport reached an impossible error state")

            if attempts >= self.config.max_retries or not self._is_retryable(last_error):
                if attempts == 0:
                    raise last_error
                raise RetryExhaustedError(
                    f"{provider_name} failed after {attempts + 1} attempts: {last_error}",
                    provider=provider_name,
                    status_code=last_error.status_code,
                    attempts=attempts + 1,
                ) from last_error

            delay = self._compute_backoff(attempts)
            self._log(
                (
                    f"[{provider_name}] retry {attempts + 1}/{self.config.max_retries} "
                    f"in {delay:.2f}s after: {last_error}"
                )
            )
            self.sleeper(delay)
            attempts += 1

    def _is_retryable(self, error: ProviderError) -> bool:
        if isinstance(error, TimeoutError):
            return True
        if error.status_code is not None:
            return error.status_code in self.config.retry_status_codes
        return "temporary network failure" in str(error).lower()

    def _compute_backoff(self, attempt: int) -> float:
        base_delay = self.config.backoff_base * (
            self.config.backoff_multiplier ** attempt
        )
        jitter = self.random_fn(0.0, self.config.jitter) if self.config.jitter else 0.0
        return min(self.config.backoff_max, base_delay + jitter)

    def _http_error(
        self,
        *,
        provider_name: str,
        response: requests.Response,
        retryable: bool,
    ) -> ProviderError:
        response_text = response.text.strip().replace("\n", " ")
        if len(response_text) > 200:
            response_text = f"{response_text[:197]}..."
        prefix = "temporary upstream failure" if retryable else "request failed"
        message = f"{provider_name} {prefix} with HTTP {response.status_code}"
        if response_text:
            message = f"{message}: {response_text}"
        return ProviderError(
            message,
            provider=provider_name,
            status_code=response.status_code,
        )

    def _log(self, message: str) -> None:
        if self.config.debug or self.config.request_logging:
            print(message)
