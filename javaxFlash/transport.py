from __future__ import annotations

from dataclasses import dataclass
import random
import time
from typing import Any

import requests

from .config import Config
from .errors import ProviderError, RetryError, TimeoutError


@dataclass(slots=True)
class NetRes:
    data: Any
    status: int
    retries: int
    latency: float


class Transport:
    def __init__(
        self,
        cfg: Config,
        *,
        session: requests.Session | None = None,
        sleep=time.sleep,
        rand=random.uniform,
    ) -> None:
        self.cfg = cfg
        self.session = session or requests.Session()
        self.sleep = sleep
        self.rand = rand

    def emit(self, event: str, **data: Any) -> None:
        for hook in self.cfg.hooks:
            hook(event, data)

    def post(
        self,
        *,
        url: str,
        data: dict[str, Any],
        provider: str,
    ) -> NetRes:
        tries = 0
        last: ProviderError | None = None

        while True:
            started = time.perf_counter()
            self.emit("request_started", provider=provider, url=url, payload=data, attempt=tries + 1)
            try:
                self._log(f"[{provider}] POST {url} json={data}")
                res = self.session.post(url, json=data, timeout=self.cfg.timeout)
                latency = (time.perf_counter() - started) * 1000

                if res.status_code in self.cfg.retry_codes:
                    raise self._http_err(provider=provider, res=res, retry=True)

                try:
                    res.raise_for_status()
                except requests.HTTPError as err:
                    raise self._http_err(provider=provider, res=res, retry=False) from err

                try:
                    body = res.json()
                except ValueError as err:
                    raise ProviderError(
                        f"{provider} returned invalid JSON",
                        provider=provider,
                        status=res.status_code,
                    ) from err

                return NetRes(data=body, status=res.status_code, retries=tries, latency=latency)

            except requests.Timeout:
                last = TimeoutError(
                    f"{provider} request timed out after {self.cfg.timeout}s",
                    provider=provider,
                )
            except requests.ConnectionError as err:
                last = ProviderError(f"{provider} temporary network failure: {err}", provider=provider)
            except ProviderError as err:
                last = err
            except requests.RequestException as err:
                last = ProviderError(f"{provider} request failed: {err}", provider=provider)

            if last is None:
                raise RuntimeError("transport reached an impossible error state")

            if tries >= self.cfg.retries or not self._can_retry(last):
                if tries == 0:
                    raise last
                raise RetryError(
                    f"{provider} failed after {tries + 1} attempts: {last}",
                    provider=provider,
                    status=last.status,
                    tries=tries + 1,
                ) from last

            delay = self._backoff(tries)
            self.emit("retry_scheduled", provider=provider, attempt=tries + 1, delay=delay, error=str(last))
            self._log(f"[{provider}] retry {tries + 1}/{self.cfg.retries} in {delay:.2f}s after: {last}")
            self.sleep(delay)
            tries += 1

    def _can_retry(self, err: ProviderError) -> bool:
        if isinstance(err, TimeoutError):
            return True
        if err.status is not None:
            return err.status in self.cfg.retry_codes
        return "temporary network failure" in str(err).lower()

    def _backoff(self, step: int) -> float:
        delay = self.cfg.backoff * (self.cfg.backoff_rate ** step)
        jitter = self.rand(0.0, self.cfg.jitter) if self.cfg.jitter else 0.0
        return min(self.cfg.backoff_max, delay + jitter)

    def _http_err(
        self,
        *,
        provider: str,
        res: requests.Response,
        retry: bool,
    ) -> ProviderError:
        text = res.text.strip().replace("\n", " ")
        if len(text) > 200:
            text = f"{text[:197]}..."
        prefix = "temporary upstream failure" if retry else "request failed"
        msg = f"{provider} {prefix} with HTTP {res.status_code}"
        if text:
            msg = f"{msg}: {text}"
        return ProviderError(msg, provider=provider, status=res.status_code)

    def _log(self, msg: str) -> None:
        if self.cfg.debug or self.cfg.log_req:
            print(msg)
