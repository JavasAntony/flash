from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Callable


ALIASES = {
    "gemini": "flash",
}
MODELS = {
    "flash": "gemini-2.0-flash-lite",
    "deepseek": "deepseek-reasoner",
}
RETRY_CODES = (408, 425, 429, 500, 502, 503, 504)


def norm_provider(name: str) -> str:
    key = name.strip().lower()
    return ALIASES.get(key, key)


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_codes(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _to_models(value: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in value.split(","):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, model = item.split("=", 1)
        out[norm_provider(name)] = model.strip()
    return out


@dataclass(slots=True)
class Config:
    timeout: float = 30.0
    retries: int = 2
    backoff: float = 0.5
    backoff_rate: float = 2.0
    backoff_max: float = 8.0
    jitter: float = 0.15
    retry_codes: tuple[int, ...] = RETRY_CODES
    provider: str = "flash"
    model: str | None = None
    models: dict[str, str] = field(default_factory=lambda: dict(MODELS))
    deepseek_temp: float = 0.7
    auto_route: bool = True
    debug: bool = False
    log_req: bool = False
    fallback: bool = True
    fallback_provider: str | None = None
    raw: bool = False
    auto_search: bool = False
    auto_tools: bool = False
    tavily_key: str | None = None
    search_tool: str = "tavily"
    search_limit: int = 5
    search_timeout: float = 20.0
    env: bool = False
    env_prefix: str = "JAVAXFLASH_"
    system: str = "You are javaxFlash, a practical, concise, and reliable AI assistant."
    hooks: tuple[Callable[[str, dict[str, Any]], None], ...] = ()

    def __post_init__(self) -> None:
        if self.env:
            self._load_env()
        self.provider = norm_provider(self.provider)
        if self.fallback_provider:
            self.fallback_provider = norm_provider(self.fallback_provider)
        self.models = {norm_provider(name): model for name, model in self.models.items()}

    @classmethod
    def from_env(cls, prefix: str = "JAVAXFLASH_", **overrides: object) -> Config:
        return cls(env=True, env_prefix=prefix, **overrides)

    @property
    def flash_model(self) -> str:
        return self.models.get("flash", MODELS["flash"])

    @property
    def main_model(self) -> str:
        return self.model or self.flash_model

    def pick_model(self, provider: str, asked: str | None = None) -> str:
        name = norm_provider(provider)
        if asked:
            return asked
        if self.model and name == self.provider:
            return self.model
        return self.models.get(name, self.model or name)

    def _load_env(self) -> None:
        env = os.environ
        pre = self.env_prefix

        floats = {
            "timeout": "TIMEOUT",
            "backoff": "BACKOFF_BASE",
            "backoff_rate": "BACKOFF_MULTIPLIER",
            "backoff_max": "BACKOFF_MAX",
            "jitter": "JITTER",
            "deepseek_temp": "DEEPSEEK_TEMPERATURE",
            "search_timeout": "SEARCH_TIMEOUT",
        }
        ints = {
            "retries": "MAX_RETRIES",
            "search_limit": "SEARCH_MAX_RESULTS",
        }
        bools = {
            "auto_route": "AUTO_ROUTE",
            "debug": "DEBUG",
            "log_req": "REQUEST_LOGGING",
            "fallback": "FALLBACK_ENABLED",
            "raw": "CAPTURE_RAW_RESPONSE",
            "auto_search": "AUTO_SEARCH",
            "auto_tools": "ENABLE_AUTO_SKILLS",
        }
        texts = {
            "provider": "DEFAULT_PROVIDER",
            "model": "DEFAULT_MODEL",
            "fallback_provider": "FALLBACK_PROVIDER",
            "system": "DEFAULT_SYSTEM_INSTRUCTION",
            "tavily_key": "TAVILY_API_KEY",
            "search_tool": "SEARCH_TOOL_NAME",
        }

        for key, suffix in floats.items():
            value = env.get(f"{pre}{suffix}")
            if value:
                setattr(self, key, float(value))

        for key, suffix in ints.items():
            value = env.get(f"{pre}{suffix}")
            if value:
                setattr(self, key, int(value))

        for key, suffix in bools.items():
            value = env.get(f"{pre}{suffix}")
            if value is not None:
                setattr(self, key, _to_bool(value))

        for key, suffix in texts.items():
            value = env.get(f"{pre}{suffix}")
            if value:
                setattr(self, key, value)

        value = env.get(f"{pre}RETRY_STATUS_CODES")
        if value:
            self.retry_codes = _to_codes(value)

        value = env.get(f"{pre}PROVIDER_MODELS")
        if value:
            self.models.update(_to_models(value))
