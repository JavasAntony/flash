from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FlashConfig:
    timeout: float = 30.0
    default_provider: str = "flash"
    default_model_name: str = "javaxFlash"
    default_gemini_model: str = "gemini-2.0-flash-lite"
    deepseek_temperature: float = 0.7
    auto_route: bool = True
    debug: bool = False
    request_logging: bool = False
    fallback_enabled: bool = True
    default_system_instruction: str = (
        "You are javaxFlash, a practical, concise, and helpful AI assistant."
    )


AIClientConfig = FlashConfig
