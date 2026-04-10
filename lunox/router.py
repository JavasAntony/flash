from __future__ import annotations

from .config import norm_provider


class Route:
    __slots__ = ("provider", "reason", "score", "signs")

    def __init__(
        self,
        provider: str,
        reason: str,
        *,
        score: int = 0,
        signs: tuple[str, ...] = (),
    ) -> None:
        self.provider = provider
        self.reason = reason
        self.score = score
        self.signs = signs


class Router:
    HARD = {
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
    EASY = (
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
        hard: set[str] | None = None,
        easy: tuple[str, ...] | None = None,
        quick_words: int = 12,
        short_q_words: int = 20,
    ) -> None:
        self.hard = hard or self.HARD
        self.easy = easy or self.EASY
        self.quick_words = quick_words
        self.short_q_words = short_q_words

    def pick(
        self,
        prompt: str,
        mode: str | None = None,
        force: str | None = None,
        auto: bool = True,
        default: str = "gemini",
    ) -> Route:
        if force:
            name = norm_provider(force)
            return Route(provider=name, reason=f"provider forced explicitly: {name}")

        text = prompt.strip().lower()
        base = norm_provider(default)

        if mode == "reasoning":
            return Route(provider="deepseek", reason="reasoning mode requested")
        if mode == "fast":
            return Route(provider="gemini", reason="fast mode requested")
        if not auto:
            return Route(provider=base, reason=f"auto routing disabled, using default provider {base}")

        score = 0
        signs: list[str] = []

        if any(token in text for token in self.hard):
            score += 2
            signs.append("complex keyword match")

        words = len(text.split())
        if words >= 40:
            score += 1
            signs.append("long prompt")

        if any(mark in text for mark in ("```", "stack", "exception", "latency")):
            score += 1
            signs.append("engineering-heavy prompt")

        if text.startswith(self.easy):
            score -= 1
            signs.append("simple prompt prefix")

        if words <= self.quick_words:
            score -= 1
            signs.append("short prompt")

        if "?" in text and words <= self.short_q_words:
            score -= 1
            signs.append("quick question")

        if score >= 2:
            return Route(
                provider="deepseek",
                reason="auto route selected deepseek for a more complex prompt",
                score=score,
                signs=tuple(signs),
            )

        return Route(
            provider="gemini",
            reason="auto route selected gemini for a lighter or direct prompt",
            score=score,
            signs=tuple(signs),
        )
