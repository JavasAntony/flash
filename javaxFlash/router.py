from __future__ import annotations

from dataclasses import dataclass, field

from .config import normalize_provider_name


@dataclass(slots=True)
class RouteDecision:
    provider: str
    reason: str
    score: int = 0
    signals: tuple[str, ...] = field(default_factory=tuple)


class FlashRouter:
    COMPLEX_KEYWORDS = {
        "debug",
        "bug",
        "error",
        "traceback",
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
        "root cause",
    }
    SIMPLE_PREFIXES = (
        "apa ",
        "what ",
        "who ",
        "when ",
        "where ",
        "define ",
        "summarize ",
        "ringkas ",
    )

    def __init__(
        self,
        *,
        complex_keywords: set[str] | None = None,
        simple_prefixes: tuple[str, ...] | None = None,
        quick_prompt_word_limit: int = 12,
        short_question_word_limit: int = 20,
    ):
        self.complex_keywords = complex_keywords or self.COMPLEX_KEYWORDS
        self.simple_prefixes = simple_prefixes or self.SIMPLE_PREFIXES
        self.quick_prompt_word_limit = quick_prompt_word_limit
        self.short_question_word_limit = short_question_word_limit

    def choose(
        self,
        prompt: str,
        mode: str | None = None,
        forced_provider: str | None = None,
        auto_route: bool = True,
        default_provider: str = "flash",
    ) -> RouteDecision:
        if forced_provider:
            canonical_provider = normalize_provider_name(forced_provider)
            return RouteDecision(
                provider=canonical_provider,
                reason=f"provider forced explicitly: {canonical_provider}",
            )

        normalized_prompt = prompt.strip().lower()
        normalized_default = normalize_provider_name(default_provider)

        if mode == "reasoning":
            return RouteDecision(
                provider="deepseek",
                reason="reasoning mode requested",
            )
        if mode == "fast":
            return RouteDecision(
                provider="flash",
                reason="fast mode requested",
            )

        if not auto_route:
            return RouteDecision(
                provider=normalized_default,
                reason=f"auto routing disabled, using default provider {normalized_default}",
            )

        signals: list[str] = []
        score = 0

        if any(token in normalized_prompt for token in self.complex_keywords):
            score += 2
            signals.append("complex keyword match")

        word_count = len(normalized_prompt.split())
        if word_count >= 40:
            score += 1
            signals.append("long prompt")

        if any(marker in normalized_prompt for marker in ("```", "stack", "exception", "latency")):
            score += 1
            signals.append("engineering-heavy prompt")

        if normalized_prompt.startswith(self.simple_prefixes):
            score -= 1
            signals.append("simple prompt prefix")

        if word_count <= self.quick_prompt_word_limit:
            score -= 1
            signals.append("short prompt")

        if "?" in normalized_prompt and word_count <= self.short_question_word_limit:
            score -= 1
            signals.append("quick question")

        if score >= 2:
            return RouteDecision(
                provider="deepseek",
                reason="auto route selected deepseek for a more complex prompt",
                score=score,
                signals=tuple(signals),
            )

        return RouteDecision(
            provider="flash",
            reason="auto route selected flash for a lighter or direct prompt",
            score=score,
            signals=tuple(signals),
        )


PromptRouter = FlashRouter
