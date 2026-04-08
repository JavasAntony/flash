from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests

from .config import FlashConfig
from .models import FlashResponse


class ProviderError(RuntimeError):
    pass


class BaseProvider(ABC):
    name: str
    endpoint: str

    def __init__(self, config: FlashConfig):
        self.config = config

    @abstractmethod
    def build_params(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def request(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> FlashResponse:
        params = self.build_params(prompt=prompt, system_prompt=system_prompt, **kwargs)
        self._log(f"[{self.name}] GET {self.endpoint} params={params}")
        try:
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ProviderError(f"{self.name} request timed out after {self.config.timeout}s") from exc
        except requests.RequestException as exc:
            raise ProviderError(f"{self.name} request failed: {exc}") from exc

        try:
            raw = response.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name} returned invalid JSON") from exc

        text = self.extract_text(raw)
        if not text:
            raise ProviderError(f"{self.name} response did not contain usable text")

        return FlashResponse(
            text=text.strip(),
            model_used=self.extract_model(raw, **kwargs),
            provider=self.name,
            raw=raw,
        )

    def extract_text(self, raw: Any) -> str:
        if isinstance(raw, str):
            return raw

        if isinstance(raw, dict):
            for key in ("text", "response", "answer", "result", "message", "content"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            data = raw.get("data")
            if isinstance(data, dict):
                for key in ("text", "response", "answer", "result", "message", "content"):
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
                parts = data.get("parts")
                if isinstance(parts, list):
                    collected: list[str] = []
                    for part in parts:
                        if isinstance(part, dict):
                            text = part.get("text")
                            if isinstance(text, str) and text.strip():
                                collected.append(text.strip())
                    if collected:
                        return "\n".join(collected)
        return ""

    def extract_model(self, raw: Any, **kwargs: Any) -> str:
        if isinstance(raw, dict):
            for key in ("model", "model_used"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return kwargs.get("model", self.name)

    def _log(self, message: str) -> None:
        if self.config.debug or self.config.request_logging:
            print(message)


class DeepSeekProvider(BaseProvider):
    name = "deepseek"
    endpoint = "https://api.siputzx.my.id/api/ai/deepseekr1"

    def build_params(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        temperature = kwargs.get("temperature", self.config.deepseek_temperature)
        return {
            "prompt": prompt,
            "system": system_prompt or self.config.default_system_instruction,
            "temperature": temperature,
        }


class FlashProvider(BaseProvider):
    name = "flash"
    endpoint = "https://api.siputzx.my.id/api/ai/gemini-lite"

    def build_params(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if system_prompt:
            prompt = f"System instruction: {system_prompt}\n\nUser request: {prompt}"
        return {
            "prompt": prompt,
            "model": kwargs.get("model", self.config.default_gemini_model),
        }

    def extract_model(self, raw: Any, **kwargs: Any) -> str:
        value = super().extract_model(raw, **kwargs)
        return self.config.default_model_name if value == self.name else value


GeminiLiteProvider = FlashProvider
