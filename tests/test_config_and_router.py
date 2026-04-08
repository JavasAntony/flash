from __future__ import annotations

from javaxFlash import FlashConfig
from javaxFlash.router import FlashRouter


def test_config_from_env_loads_retry_and_provider_settings(monkeypatch) -> None:
    monkeypatch.setenv("JAVAXFLASH_TIMEOUT", "15")
    monkeypatch.setenv("JAVAXFLASH_MAX_RETRIES", "4")
    monkeypatch.setenv("JAVAXFLASH_DEFAULT_PROVIDER", "gemini")
    monkeypatch.setenv("JAVAXFLASH_FALLBACK_PROVIDER", "deepseek")
    monkeypatch.setenv("JAVAXFLASH_PROVIDER_MODELS", "flash=gemini-2.5-flash,deepseek=deepseek-r1")

    config = FlashConfig.from_env()

    assert config.timeout == 15.0
    assert config.max_retries == 4
    assert config.default_provider == "flash"
    assert config.fallback_provider == "deepseek"
    assert config.default_gemini_model == "gemini-2.5-flash"


def test_resolve_model_prefers_explicit_default_for_default_provider() -> None:
    config = FlashConfig(default_provider="flash", default_model="flash-custom")

    assert config.resolve_model("flash") == "flash-custom"
    assert config.resolve_model("deepseek") == config.provider_models["deepseek"]


def test_router_prefers_deepseek_for_complex_prompt() -> None:
    router = FlashRouter()

    decision = router.choose(
        prompt="Analyze the architecture and debug the latency bottleneck in this service.",
        auto_route=True,
    )

    assert decision.provider == "deepseek"
    assert "complex" in decision.reason.lower()
    assert "complex keyword match" in decision.signals


def test_router_uses_default_provider_when_auto_route_is_disabled() -> None:
    router = FlashRouter()

    decision = router.choose(
        prompt="What is Python?",
        auto_route=False,
        default_provider="gemini",
    )

    assert decision.provider == "flash"
    assert decision.reason == "auto routing disabled, using default provider flash"
