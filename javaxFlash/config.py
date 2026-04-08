from __future__ import annotations

from dataclasses import dataclass, field
import os


PROVIDER_ALIASES = {
    "gemini": "flash",
}
DEFAULT_PROVIDER_MODELS = {
    "flash": "gemini-2.0-flash-lite",
    "deepseek": "deepseek-reasoner",
}
DEFAULT_RETRY_STATUS_CODES = (408, 425, 429, 500, 502, 503, 504)


def normalize_provider_name(provider: str) -> str:
    normalized = provider.strip().lower()
    return PROVIDER_ALIASES.get(normalized, normalized)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_status_codes(value: str) -> tuple[int, ...]:
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def _parse_provider_models(value: str) -> dict[str, str]:
    models: dict[str, str] = {}
    for item in value.split(","):
        chunk = item.strip()
        if not chunk or "=" not in chunk:
            continue
        provider, model = chunk.split("=", 1)
        models[normalize_provider_name(provider)] = model.strip()
    return models


@dataclass(slots=True)
class FlashConfig:
    timeout: float = 30.0
    max_retries: int = 2
    backoff_base: float = 0.5
    backoff_multiplier: float = 2.0
    backoff_max: float = 8.0
    jitter: float = 0.15
    retry_status_codes: tuple[int, ...] = DEFAULT_RETRY_STATUS_CODES
    default_provider: str = "flash"
    default_model: str | None = None
    provider_models: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_PROVIDER_MODELS)
    )
    deepseek_temperature: float = 0.7
    auto_route: bool = True
    debug: bool = False
    request_logging: bool = False
    fallback_enabled: bool = True
    fallback_provider: str | None = None
    capture_raw_response: bool = False
    auto_search: bool = False
    tavily_api_key: str | None = None
    search_tool_name: str = "tavily"
    search_max_results: int = 5
    search_timeout: float = 20.0
    load_from_env: bool = False
    env_prefix: str = "JAVAXFLASH_"
    default_system_instruction: str = (
        "You are javaxFlash, a practical, concise, and reliable AI assistant."
    )

    def __post_init__(self) -> None:
        if self.load_from_env:
            self._apply_env_overrides()

        self.default_provider = normalize_provider_name(self.default_provider)
        if self.fallback_provider:
            self.fallback_provider = normalize_provider_name(self.fallback_provider)
        self.provider_models = {
            normalize_provider_name(provider): model
            for provider, model in self.provider_models.items()
        }

    @classmethod
    def from_env(cls, prefix: str = "JAVAXFLASH_", **overrides: object) -> FlashConfig:
        return cls(load_from_env=True, env_prefix=prefix, **overrides)

    @property
    def default_gemini_model(self) -> str:
        return self.provider_models.get("flash", DEFAULT_PROVIDER_MODELS["flash"])

    @property
    def default_model_name(self) -> str:
        return self.default_model or self.default_gemini_model

    def resolve_model(self, provider: str, requested_model: str | None = None) -> str:
        canonical_provider = normalize_provider_name(provider)
        if requested_model:
            return requested_model
        if self.default_model and canonical_provider == self.default_provider:
            return self.default_model
        return self.provider_models.get(
            canonical_provider,
            self.default_model or canonical_provider,
        )

    def _apply_env_overrides(self) -> None:
        prefix = self.env_prefix
        env = os.environ

        float_fields = {
            "timeout": "TIMEOUT",
            "backoff_base": "BACKOFF_BASE",
            "backoff_multiplier": "BACKOFF_MULTIPLIER",
            "backoff_max": "BACKOFF_MAX",
            "jitter": "JITTER",
            "deepseek_temperature": "DEEPSEEK_TEMPERATURE",
        }
        int_fields = {
            "max_retries": "MAX_RETRIES",
        }
        bool_fields = {
            "auto_route": "AUTO_ROUTE",
            "debug": "DEBUG",
            "request_logging": "REQUEST_LOGGING",
            "fallback_enabled": "FALLBACK_ENABLED",
            "capture_raw_response": "CAPTURE_RAW_RESPONSE",
            "auto_search": "AUTO_SEARCH",
        }
        str_fields = {
            "default_provider": "DEFAULT_PROVIDER",
            "default_model": "DEFAULT_MODEL",
            "fallback_provider": "FALLBACK_PROVIDER",
            "default_system_instruction": "DEFAULT_SYSTEM_INSTRUCTION",
            "tavily_api_key": "TAVILY_API_KEY",
            "search_tool_name": "SEARCH_TOOL_NAME",
        }
        int_fields.update(
            {
                "search_max_results": "SEARCH_MAX_RESULTS",
            }
        )
        float_fields.update(
            {
                "search_timeout": "SEARCH_TIMEOUT",
            }
        )

        for field_name, suffix in float_fields.items():
            raw_value = env.get(f"{prefix}{suffix}")
            if raw_value:
                setattr(self, field_name, float(raw_value))

        for field_name, suffix in int_fields.items():
            raw_value = env.get(f"{prefix}{suffix}")
            if raw_value:
                setattr(self, field_name, int(raw_value))

        for field_name, suffix in bool_fields.items():
            raw_value = env.get(f"{prefix}{suffix}")
            if raw_value is not None:
                setattr(self, field_name, _parse_bool(raw_value))

        for field_name, suffix in str_fields.items():
            raw_value = env.get(f"{prefix}{suffix}")
            if raw_value:
                setattr(self, field_name, raw_value)

        raw_status_codes = env.get(f"{prefix}RETRY_STATUS_CODES")
        if raw_status_codes:
            self.retry_status_codes = _parse_status_codes(raw_status_codes)

        raw_provider_models = env.get(f"{prefix}PROVIDER_MODELS")
        if raw_provider_models:
            self.provider_models.update(_parse_provider_models(raw_provider_models))


AIClientConfig = FlashConfig
