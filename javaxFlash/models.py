from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import SchemaLike


@dataclass(slots=True)
class FlashRequest:
    prompt: str
    system_instruction: str | None = None
    model: str | None = None
    include_raw: bool = False
    schema: SchemaLike | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FlashResponse:
    text: str
    provider: str
    model_used: str
    route_reason: str = ""
    retry_count: int = 0
    latency_ms: float | None = None
    raw: Any = None
    structured_output: Any = None
    search_used: bool = False
    search_query: str | None = None
    search_summary: str | None = None
    skills_used: tuple[str, ...] = ()
    skills_summary: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


AIResponse = FlashResponse
