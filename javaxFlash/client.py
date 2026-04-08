from __future__ import annotations

from typing import Any

from .config import FlashConfig
from .models import FlashResponse
from .providers import DeepSeekProvider, FlashProvider, ProviderError
from .router import FlashRouter


class FlashClient:
    def __init__(self, config: FlashConfig | None = None):
        self.config = config or FlashConfig()
        self.router = FlashRouter()
        self.providers = {
            "deepseek": DeepSeekProvider(self.config),
            "gemini": FlashProvider(self.config),
            "flash": FlashProvider(self.config),
        }

    def flash(
        self,
        prompt: str,
        *,
        mode: str | None = None,
        provider: str | None = None,
        auto_route: bool | None = None,
        system_instruction: str | None = None,
        fallback_provider: str | None = None,
        **kwargs: Any,
    ) -> FlashResponse:
        auto_route = self.config.auto_route if auto_route is None else auto_route
        if provider == "flash":
            provider = "gemini"
        if fallback_provider == "flash":
            fallback_provider = "gemini"
        instruction = system_instruction or self.config.default_system_instruction

        decision = self.router.choose(
            prompt=prompt,
            mode=mode,
            forced_provider=provider,
            auto_route=auto_route,
            default_provider=self.config.default_provider,
        )
        chosen_provider = decision.provider

        try:
            response = self.providers[chosen_provider].request(
                prompt,
                system_prompt=instruction,
                **kwargs,
            )
            response.route_reason = decision.reason
            response.provider = "flash" if chosen_provider == "gemini" else chosen_provider
        except ProviderError as exc:
            if not self.config.fallback_enabled and not fallback_provider:
                return self._error_response(chosen_provider, str(exc), decision.reason)
            backup = fallback_provider or self._other_provider(chosen_provider)
            try:
                response = self.providers[backup].request(
                    prompt,
                    system_prompt=instruction,
                    **kwargs,
                )
                response.route_reason = f"{decision.reason}; fallback to {backup} after {chosen_provider} failed"
                response.provider = "flash" if backup == "gemini" else backup
            except ProviderError as fallback_exc:
                return self._error_response(
                    chosen_provider,
                    f"{exc} | fallback failed: {fallback_exc}",
                    decision.reason,
                )

        return response

    def ask(self, prompt: str, **kwargs: Any) -> FlashResponse:
        return self.flash(prompt, **kwargs)

    def _other_provider(self, provider: str) -> str:
        return "gemini" if provider == "deepseek" else "deepseek"

    def _error_response(
        self,
        provider: str,
        error: str,
        route_reason: str,
    ) -> FlashResponse:
        public_provider = "flash" if provider == "gemini" else provider
        return FlashResponse(
            text="",
            model_used=self.config.default_model_name if public_provider == "flash" else provider,
            provider=public_provider,
            raw=None,
            route_reason=route_reason,
            error=error,
        )


AIClient = FlashClient
