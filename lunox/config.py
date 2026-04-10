from __future__ import annotations

import os
from typing import Any, Callable


ALIASES = {
    "flash": "gemini",
}
MODELS = {
    "gemini": "gemini-2.0-flash-lite",
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


class Config:
    __slots__ = (
        "timeout",
        "retries",
        "backoff",
        "backoff_rate",
        "backoff_max",
        "jitter",
        "retry_codes",
        "provider",
        "model",
        "models",
        "deepseek_temp",
        "auto_route",
        "debug",
        "log_req",
        "fallback",
        "fallback_provider",
        "raw",
        "auto_search",
        "auto_tools",
        "tavily_key",
        "search_tool",
        "search_limit",
        "search_timeout",
        "env",
        "env_prefix",
        "custom_instruction",
        "hooks",
    )

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        retries: int = 2,
        backoff: float = 0.5,
        backoff_rate: float = 2.0,
        backoff_max: float = 8.0,
        jitter: float = 0.15,
        retry_codes: tuple[int, ...] = RETRY_CODES,
        provider: str = "gemini",
        model: str | None = None,
        models: dict[str, str] | None = None,
        deepseek_temp: float = 0.7,
        auto_route: bool = True,
        debug: bool = False,
        log_req: bool = False,
        fallback: bool = True,
        fallback_provider: str | None = None,
        raw: bool = False,
        auto_search: bool = False,
        auto_tools: bool = False,
        tavily_key: str | None = None,
        search_tool: str = "tavily",
        search_limit: int = 5,
        search_timeout: float = 20.0,
        env: bool = False,
        env_prefix: str = "LUNOX_",
        custom_instruction: str = "You are Lunox, a practical, concise, and reliable AI assistant.",
        system: str | None = None,
        hooks: tuple[Callable[[str, dict[str, Any]], None], ...] = (),
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.backoff_rate = backoff_rate
        self.backoff_max = backoff_max
        self.jitter = jitter
        self.retry_codes = retry_codes
        self.provider = provider
        self.model = model
        self.models = dict(MODELS if models is None else models)
        self.deepseek_temp = deepseek_temp
        self.auto_route = auto_route
        self.debug = debug
        self.log_req = log_req
        self.fallback = fallback
        self.fallback_provider = fallback_provider
        self.raw = raw
        self.auto_search = auto_search
        self.auto_tools = auto_tools
        self.tavily_key = tavily_key
        self.search_tool = search_tool
        self.search_limit = search_limit
        self.search_timeout = search_timeout
        self.env = env
        self.env_prefix = env_prefix
        self.custom_instruction = system or custom_instruction
        self.hooks = hooks
        self._finalize()

    def _finalize(self) -> None:
        if self.env:
            self._load_env()
        self.provider = norm_provider(self.provider)
        if self.fallback_provider:
            self.fallback_provider = norm_provider(self.fallback_provider)
        self.models = {norm_provider(name): model for name, model in self.models.items()}

    @classmethod
    def from_env(cls, prefix: str = "LUNOX_", **overrides: object) -> Config:
        return cls(env=True, env_prefix=prefix, **overrides)

    @property
    def gemini_model(self) -> str:
        return self.models.get("gemini", MODELS["gemini"])

    @property
    def main_model(self) -> str:
        return self.model or self.gemini_model

    @property
    def system(self) -> str:
        return self.custom_instruction

    @system.setter
    def system(self, value: str) -> None:
        self.custom_instruction = value

    def set_instruction(self, text: str) -> Config:
        self.custom_instruction = text.strip()
        return self

    def set_provider(self, provider: str, model: str | None = None) -> Config:
        self.provider = norm_provider(provider)
        if model is not None:
            self.model = model
        return self

    def enable_search(self, *, auto_search: bool = True, auto_tools: bool = True) -> Config:
        self.auto_search = auto_search
        self.auto_tools = auto_tools
        return self

    def set_retry_policy(
        self,
        *,
        retries: int | None = None,
        backoff: float | None = None,
        backoff_rate: float | None = None,
        backoff_max: float | None = None,
        jitter: float | None = None,
    ) -> Config:
        if retries is not None:
            self.retries = retries
        if backoff is not None:
            self.backoff = backoff
        if backoff_rate is not None:
            self.backoff_rate = backoff_rate
        if backoff_max is not None:
            self.backoff_max = backoff_max
        if jitter is not None:
            self.jitter = jitter
        return self

    def use_tavily(self, api_key: str, *, tool_name: str = "tavily", limit: int | None = None) -> Config:
        self.tavily_key = api_key
        self.search_tool = tool_name
        if limit is not None:
            self.search_limit = limit
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "timeout": self.timeout,
            "retries": self.retries,
            "backoff": self.backoff,
            "backoff_rate": self.backoff_rate,
            "backoff_max": self.backoff_max,
            "jitter": self.jitter,
            "retry_codes": self.retry_codes,
            "provider": self.provider,
            "model": self.model,
            "models": dict(self.models),
            "deepseek_temp": self.deepseek_temp,
            "auto_route": self.auto_route,
            "debug": self.debug,
            "log_req": self.log_req,
            "fallback": self.fallback,
            "fallback_provider": self.fallback_provider,
            "raw": self.raw,
            "auto_search": self.auto_search,
            "auto_tools": self.auto_tools,
            "tavily_key": self.tavily_key,
            "search_tool": self.search_tool,
            "search_limit": self.search_limit,
            "search_timeout": self.search_timeout,
            "env": self.env,
            "env_prefix": self.env_prefix,
            "custom_instruction": self.custom_instruction,
        }

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
            "custom_instruction": "DEFAULT_SYSTEM_INSTRUCTION",
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
