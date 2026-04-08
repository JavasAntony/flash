from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .config import FlashConfig, normalize_provider_name
from .errors import ProviderError, ProviderNotFoundError
from .models import FlashRequest, FlashResponse
from .transport import HttpTransport


class BaseProvider(ABC):
    name: str
    endpoint: str

    def __init__(self, config: FlashConfig, transport: HttpTransport):
        self.config = config
        self.transport = transport

    def generate(self, request: FlashRequest) -> FlashResponse:
        payload = self.build_payload(request)
        result = self.transport.post_json(
            url=self.endpoint,
            payload=payload,
            provider_name=self.name,
        )
        raw = result.payload
        text = self.extract_text(raw)
        if not text:
            raise ProviderError(
                f"{self.name} response did not contain usable text",
                provider=self.name,
            )

        return FlashResponse(
            text=text.strip(),
            provider=self.name,
            model_used=self.extract_model(raw, request),
            retry_count=result.retry_count,
            latency_ms=result.latency_ms,
            raw=raw if request.include_raw else None,
        )

    @abstractmethod
    def build_payload(self, request: FlashRequest) -> dict[str, Any]:
        raise NotImplementedError

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
                return self.extract_text(data)

            candidates = raw.get("candidates")
            if isinstance(candidates, list):
                collected: list[str] = []
                for candidate in candidates:
                    if isinstance(candidate, dict):
                        text = self.extract_text(candidate)
                        if text:
                            collected.append(text)
                if collected:
                    return "\n".join(collected)

            parts = raw.get("parts")
            if isinstance(parts, list):
                collected = []
                for part in parts:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            collected.append(text.strip())
                if collected:
                    return "\n".join(collected)

        if isinstance(raw, list):
            collected = [self.extract_text(item) for item in raw]
            collected = [item for item in collected if item]
            if collected:
                return "\n".join(collected)

        return ""

    def extract_model(self, raw: Any, request: FlashRequest) -> str:
        if isinstance(raw, dict):
            for key in ("model", "model_used"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return self.config.resolve_model(self.name, request.model)


class FlashProvider(BaseProvider):
    name = "flash"
    endpoint = "https://api.siputzx.my.id/api/ai/gemini-lite"

    def build_payload(self, request: FlashRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "prompt": request.prompt,
            "model": self.config.resolve_model(self.name, request.model),
        }
        if request.system_instruction:
            payload["system"] = request.system_instruction
        temperature = request.options.get("temperature")
        if temperature is not None:
            payload["temperature"] = temperature
        return payload


class DeepSeekProvider(BaseProvider):
    name = "deepseek"
    endpoint = "https://api.siputzx.my.id/api/ai/deepseekr1"

    def build_payload(self, request: FlashRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "prompt": request.prompt,
            "model": self.config.resolve_model(self.name, request.model),
            "system": request.system_instruction or self.config.default_system_instruction,
            "temperature": request.options.get(
                "temperature",
                self.config.deepseek_temperature,
            ),
        }
        return payload


class ProviderRegistry:
    def __init__(self, providers: list[BaseProvider] | tuple[BaseProvider, ...]):
        self.providers: dict[str, BaseProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: BaseProvider) -> None:
        self.providers[provider.name] = provider

    def get(self, name: str) -> BaseProvider:
        canonical_name = normalize_provider_name(name)
        try:
            return self.providers[canonical_name]
        except KeyError as exc:
            raise ProviderNotFoundError(
                f"Unknown provider '{name}'. Available providers: {', '.join(sorted(self.providers))}",
                provider=canonical_name,
            ) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.providers))


GeminiLiteProvider = FlashProvider
