from __future__ import annotations

from javaxFlash import Config
from javaxFlash.router import Router


def test_config_from_env_loads_retry_and_provider_settings(monkeypatch) -> None:
    monkeypatch.setenv("JAVAXFLASH_TIMEOUT", "15")
    monkeypatch.setenv("JAVAXFLASH_MAX_RETRIES", "4")
    monkeypatch.setenv("JAVAXFLASH_DEFAULT_PROVIDER", "gemini")
    monkeypatch.setenv("JAVAXFLASH_FALLBACK_PROVIDER", "deepseek")
    monkeypatch.setenv("JAVAXFLASH_PROVIDER_MODELS", "flash=gemini-2.5-flash,deepseek=deepseek-r1")

    cfg = Config.from_env()

    assert cfg.timeout == 15.0
    assert cfg.retries == 4
    assert cfg.provider == "flash"
    assert cfg.fallback_provider == "deepseek"
    assert cfg.flash_model == "gemini-2.5-flash"


def test_pick_model_prefers_explicit_default_for_main_provider() -> None:
    cfg = Config(provider="flash", model="flash-custom")

    assert cfg.pick_model("flash") == "flash-custom"
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

    assert route.provider == "flash"
    assert route.reason == "auto routing disabled, using default provider flash"
