from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RouteDecision:
    provider: str
    reason: str


class FlashRouter:
    COMPLEX_KEYWORDS = {
        "debug",
        "bug",
        "error",
        "reasoning",
        "step-by-step",
        "step by step",
        "architecture",
        "design",
        "plan",
        "strategy",
        "analyze",
        "analysis",
        "compare",
        "tradeoff",
        "why",
        "kenapa",
        "mengapa",
        "refactor",
        "algorithm",
        "infinite loop",
        "q-learning",
        "rl",
        "root cause",
    }
    SIMPLE_PREFIXES = (
        "apa ",
        "what ",
        "who ",
        "when ",
        "where ",
        "define ",
        "jelaskan singkat",
        "summarize ",
        "ringkas ",
    )

    def choose(
        self,
        prompt: str,
        mode: str | None = None,
        forced_provider: str | None = None,
        auto_route: bool = True,
        default_provider: str = "flash",
    ) -> RouteDecision:
        if forced_provider == "flash":
            forced_provider = "gemini"

        if forced_provider:
            return RouteDecision(
                provider=forced_provider,
                reason=f"provider forced explicitly: {forced_provider}",
            )

        if mode == "reasoning":
            return RouteDecision(provider="deepseek", reason="reasoning mode requested")
        if mode == "fast":
            return RouteDecision(provider="gemini", reason="fast mode requested (Flash)")

        if not auto_route:
            resolved = "gemini" if default_provider == "flash" else default_provider
            return RouteDecision(
                provider=resolved,
                reason=f"auto routing disabled, using default provider {default_provider}",
            )

        normalized = prompt.strip().lower()
        if any(token in normalized for token in self.COMPLEX_KEYWORDS):
            return RouteDecision(
                provider="deepseek",
                reason="prompt contains complex reasoning/debugging keywords",
            )
        if len(normalized.split()) <= 12 or normalized.startswith(self.SIMPLE_PREFIXES):
            return RouteDecision(
                provider="gemini",
                reason="prompt looks short or fact-oriented",
            )
        if "?" in normalized and len(normalized.split()) <= 20:
            return RouteDecision(
                provider="gemini",
                reason="prompt looks like a quick question",
            )
        return RouteDecision(
            provider="deepseek",
            reason="defaulted to deeper reasoning for broader prompt",
        )


PromptRouter = FlashRouter
