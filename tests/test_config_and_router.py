from __future__ import annotations

from lunox import Config
from lunox.router import Router


def test_config_from_env_loads_retry_and_provider_settings(monkeypatch) -> None:
    monkeypatch.setenv("LUNOX_TIMEOUT", "15")
    monkeypatch.setenv("LUNOX_MAX_RETRIES", "4")
    monkeypatch.setenv("LUNOX_DEFAULT_PROVIDER", "gemini")
    monkeypatch.setenv("LUNOX_FALLBACK_PROVIDER", "deepseek")
    monkeypatch.setenv("LUNOX_PROVIDER_MODELS", "gemini=gemini-2.5-flash,deepseek=deepseek-r1")

    cfg = Config.from_env()

    assert cfg.timeout == 15.0
    assert cfg.retries == 4
    assert cfg.provider == "gemini"
    assert cfg.fallback_provider == "deepseek"
    assert cfg.gemini_model == "gemini-2.5-flash"


def test_pick_model_prefers_explicit_default_for_main_provider() -> None:
    cfg = Config(provider="gemini", model="gemini-custom")

    assert cfg.pick_model("gemini") == "gemini-custom"
    assert cfg.pick_model("deepseek") == cfg.models["deepseek"]


def test_router_prefers_deepseek_for_complex_prompt() -> None:
    router = Router()

    route = router.pick(
        prompt="Analyze the architecture and debug the latency bottleneck in this service.",
        auto=True,
    )

    assert route.provider == "deepseek"
    assert "complex" in route.reason.lower()
    assert "complex keyword match" in route.signs


def test_router_uses_main_provider_when_auto_route_is_disabled() -> None:
    router = Router()

    route = router.pick(
        prompt="What is Python?",
        auto=False,
        default="gemini",
    )

    assert route.provider == "gemini"
    assert route.reason == "auto routing disabled, using default provider gemini"
