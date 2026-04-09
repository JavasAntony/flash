from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema import SchemaLike


@dataclass(slots=True, frozen=True)
class Caps:
    system: bool = True
    schema: bool = True
    tools: bool = True
    ctx: int | None = None
    cost: str = "standard"


@dataclass(slots=True)
class Req:
    prompt: str
    system: str | None = None
    model: str | None = None
    raw: bool = False
    schema: SchemaLike | None = None
    opts: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Res:
    text: str
    provider: str
    model: str
    reason: str = ""
    retries: int = 0
    latency: float | None = None
    raw: Any = None
    think: str | None = None
    data: Any = None
    searched: bool = False
    search_query: str | None = None
    search_note: str | None = None
    skills: tuple[str, ...] = ()
    skill_note: str | None = None
    tools: tuple[str, ...] = ()
    caps: Caps | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
