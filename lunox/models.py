from __future__ import annotations

from typing import Any

from .schema import SchemaLike


class Caps:
    __slots__ = ("system", "schema", "tools", "ctx", "cost")

    def __init__(
        self,
        *,
        system: bool = True,
        schema: bool = True,
        tools: bool = True,
        ctx: int | None = None,
        cost: str = "standard",
    ) -> None:
        self.system = system
        self.schema = schema
        self.tools = tools
        self.ctx = ctx
        self.cost = cost

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Caps):
            return NotImplemented
        return (
            self.system == other.system
            and self.schema == other.schema
            and self.tools == other.tools
            and self.ctx == other.ctx
            and self.cost == other.cost
        )


class Req:
    __slots__ = ("prompt", "system", "model", "raw", "schema", "opts")

    def __init__(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        raw: bool = False,
        schema: SchemaLike | None = None,
        opts: dict[str, Any] | None = None,
    ) -> None:
        self.prompt = prompt
        self.system = system
        self.model = model
        self.raw = raw
        self.schema = schema
        self.opts = {} if opts is None else opts


class Res:
    __slots__ = (
        "text",
        "provider",
        "model",
        "reason",
        "retries",
        "latency",
        "raw",
        "think",
        "data",
        "searched",
        "search_query",
        "search_note",
        "skills",
        "skill_note",
        "tools",
        "caps",
        "error",
    )

    def __init__(
        self,
        text: str,
        *,
        provider: str,
        model: str,
        reason: str = "",
        retries: int = 0,
        latency: float | None = None,
        raw: Any = None,
        think: str | None = None,
        data: Any = None,
        searched: bool = False,
        search_query: str | None = None,
        search_note: str | None = None,
        skills: tuple[str, ...] = (),
        skill_note: str | None = None,
        tools: tuple[str, ...] = (),
        caps: Caps | None = None,
        error: str | None = None,
    ) -> None:
        self.text = text
        self.provider = provider
        self.model = model
        self.reason = reason
        self.retries = retries
        self.latency = latency
        self.raw = raw
        self.think = think
        self.data = data
        self.searched = searched
        self.search_query = search_query
        self.search_note = search_note
        self.skills = skills
        self.skill_note = skill_note
        self.tools = tools
        self.caps = caps
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None
