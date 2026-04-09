from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .config import Config, norm_provider
from .errors import MissingProviderError, ProviderError
from .models import Caps, Req, Res
from .providers import DeepSeek, Flash, ProviderMap
from .router import Router
from .schema import SchemaLike, parse_json, schema_note
from .tools import FuncTool, Tavily, Tool, ToolMap, ToolRes
from .transport import Transport


class Client:
    def __init__(
        self,
        cfg: Config | None = None,
        *,
        router: Router | None = None,
        net: Transport | None = None,
        providers: list | tuple | None = None,
        tools: ToolMap | None = None,
    ) -> None:
        self.cfg = cfg or Config()
        self.net = net or Transport(self.cfg)
        self.router = router or Router()
        self.tools = tools or ToolMap()
        self.provider_map = ProviderMap(
            providers or (Flash(self.cfg, self.net), DeepSeek(self.cfg, self.net))
        )
        self.providers = self.provider_map.items

    def flash(
        self,
        prompt: str,
        *,
        mode: str | None = None,
        provider: str | None = None,
        auto_route: bool | None = None,
        system: str | None = None,
        fallback: str | None = None,
        model: str | None = None,
        schema: SchemaLike | None = None,
        raw: bool | None = None,
        skills: str | list[str] | tuple[str, ...] | None = None,
        use_search: bool | None = None,
        auto_tools: bool | None = None,
        search_query: str | None = None,
        urls: str | list[str] | tuple[str, ...] | None = None,
        tool_calls: dict[str, dict[str, Any]] | None = None,
        **opts: Any,
    ) -> Res:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")

        auto = self.cfg.auto_route if auto_route is None else auto_route
        forced = norm_provider(provider) if provider else None
        backup = self._fallback_name(fallback)
        route = self.router.pick(
            prompt=prompt,
            mode=mode,
            force=forced,
            auto=auto,
            default=self.cfg.provider,
        )

        req = Req(
            prompt=prompt,
            system=self._system(system, schema),
            model=model,
            raw=self.cfg.raw if raw is None else raw,
            schema=schema,
            opts=dict(opts),
        )
        self._emit(
            "flash_requested",
            prompt=prompt,
            provider=forced or route.provider,
            mode=mode,
            schema_used=schema is not None,
        )
        skill_ctx = self._skill_ctx(
            prompt=prompt,
            skills=skills,
            use_search=use_search,
            auto_tools=auto_tools,
            search_query=search_query,
            urls=urls,
        )
        tool_ctx = self._tool_ctx(tool_calls)
        req.prompt = self._prompt(prompt, schema, skill_ctx, tool_ctx)

        try:
            res = self.provider_map.get(route.provider).run(req)
        except ProviderError as err:
            if not self._can_fallback(route.provider, backup):
                raise
            self._emit(
                "fallback_triggered",
                provider=route.provider,
                fallback_provider=backup or self._other(route.provider),
                error=str(err),
            )
            res = self._fallback(
                req=req,
                provider=route.provider,
                backup=backup or self._other(route.provider),
                err=err,
                reason=route.reason,
            )
        else:
            res.reason = route.reason

        if schema is not None:
            res.data = parse_json(res.text, schema)
        if skill_ctx is not None:
            res.skills = tuple(skill_ctx["skills"])
            res.skill_note = skill_ctx["text"]
        if skill_ctx is not None and "search" in skill_ctx["skills"]:
            res.searched = True
            res.search_query = skill_ctx.get("search_query")
            res.search_note = skill_ctx["text"]
        if tool_ctx is not None:
            res.tools = tuple(tool_ctx["tools"])
        res.caps = self.provider_map.caps_for(res.provider)
        self._emit(
            "response_received",
            provider=res.provider,
            model=res.model,
            latency_ms=res.latency,
            retry_count=res.retries,
        )
        return res

    def ask(self, prompt: str, **kwargs: Any) -> Res:
        return self.flash(prompt, **kwargs)

    def add_tool(self, tool: Tool) -> Tool:
        self.tools.add(tool)
        return tool

    def register_tool(self, tool: Tool) -> Tool:
        return self.add_tool(tool)

    def add_fn(
        self,
        name: str,
        fn: Any,
        *,
        desc: str = "",
        fmt: Any = None,
    ) -> Tool:
        return self.add_tool(FuncTool(name, fn, desc=desc, fmt=fmt))

    def register_function(
        self,
        name: str,
        func: Any,
        *,
        description: str = "",
        formatter: Any = None,
    ) -> Tool:
        return self.add_fn(name, func, desc=description, fmt=formatter)

    def get_tool(self, name: str) -> Tool:
        return self.tools.get(name)

    def list_tools(self) -> tuple[str, ...]:
        return self.tools.names()

    def run_tool(self, name: str, **kwargs: Any) -> Any:
        return self.tools.run(name, **kwargs)

    def session(self, *, system: str | None = None, max_turns: int | None = None) -> Session:
        return Session(client=self, system=system, max_turns=max_turns)

    def list_providers(self) -> tuple[str, ...]:
        return self.provider_map.names()

    def get_caps(self, provider: str) -> Caps:
        return self.provider_map.caps_for(provider)

    def search(self, query: str, *, limit: int = 5, tool: str | None = None) -> str:
        return self._skill_text("search", self._skill_tool(tool, "search").search(query=query, limit=limit))

    def extract(self, url: str, *, tool: str | None = None) -> str:
        return self._skill_text("extract", self._skill_tool(tool, "extract").extract(url))

    def use_tavily(
        self,
        api_key: str | None = None,
        *,
        tool: str = "tavily",
        topic: str = "general",
        depth: str = "basic",
        answer: bool = True,
        raw: bool = False,
    ) -> Tool:
        item = Tavily(
            api_key=api_key or self.cfg.tavily_key,
            topic=topic,
            depth=depth,
            answer=answer,
            raw=raw,
        )
        item.name = tool
        return self.add_tool(item)

    def _fallback(self, *, req: Req, provider: str, backup: str, err: ProviderError, reason: str) -> Res:
        try:
            res = self.provider_map.get(backup).run(req)
        except ProviderError as next_err:
            raise ProviderError(
                f"{provider} failed: {err}. Fallback provider {backup} also failed: {next_err}",
                provider=backup,
            ) from next_err
        res.reason = f"{reason}; fallback to {backup} after {provider} failed"
        return res

    def _fallback_name(self, name: str | None) -> str | None:
        out = name or self.cfg.fallback_provider
        if not out:
            return None
        return norm_provider(out)

    def _prompt(
        self,
        prompt: str,
        schema: SchemaLike | None,
        skill_ctx: dict[str, Any] | None,
        tool_ctx: dict[str, Any] | None,
    ) -> str:
        parts = [prompt.rstrip()]
        if skill_ctx is not None:
            parts.append(
                "\n".join(
                    [
                        "Use the following skill-derived grounding as factual context when answering.",
                        "Rely on this context where relevant, but keep the final answer natural and concise.",
                        skill_ctx["text"],
                    ]
                )
            )
        if tool_ctx is not None:
            parts.append(
                "\n".join(
                    [
                        "Use the following local tool results as additional context when useful.",
                        tool_ctx["text"],
                    ]
                )
            )
        if schema is not None:
            parts.append(schema_note(schema))
        return "\n\n".join(part for part in parts if part)

    def _system(self, system: str | None, schema: SchemaLike | None) -> str:
        text = system or self.cfg.system
        if schema is None:
            return text
        return f"{text.rstrip()}\nReturn only valid JSON with no markdown fences or extra commentary."

    def _emit(self, event: str, **data: Any) -> None:
        for hook in self.cfg.hooks:
            hook(event, data)

    def _skill_ctx(
        self,
        *,
        prompt: str,
        skills: str | list[str] | tuple[str, ...] | None,
        use_search: bool | None,
        auto_tools: bool | None,
        search_query: str | None,
        urls: str | list[str] | tuple[str, ...] | None,
    ) -> dict[str, Any] | None:
        picks = self._skills(prompt, skills, use_search, auto_tools)
        if not picks:
            return None
        self._ensure_tavily()
        tool = self._skill_tool(None, "search")
        clean_urls = self._urls(urls, prompt)
        if "extract" in picks and not clean_urls:
            raise ValueError("extract skill requires at least one URL in urls or the prompt")

        out: list[tuple[str, ToolRes]] = []
        for skill in picks:
            if skill == "search":
                query = search_query or prompt
                out.append((skill, tool.search(query=query, limit=self.cfg.search_limit)))
            elif skill == "extract":
                tool = self._skill_tool(None, "extract")
                for url in clean_urls:
                    out.append((skill, tool.extract(url)))

        if not out:
            return None
        text = self._skill_ctx_text(out)
        data: dict[str, Any] = {"skills": picks, "text": text}
        if "search" in picks:
            data["search_query"] = search_query or prompt
        return data

    def _tool_ctx(self, calls: dict[str, dict[str, Any]] | None) -> dict[str, Any] | None:
        if not calls:
            return None
        out: list[tuple[str, ToolRes]] = []
        for name, kwargs in calls.items():
            args = kwargs if isinstance(kwargs, dict) else {}
            res = self.run_tool(name, **args)
            self._emit("tool_called", tool=name, kwargs=args)
            out.append((name, res))
        names: list[str] = []
        lines = ["Local tool results:"]
        for name, res in out:
            names.append(name)
            lines.append(res.as_text(f"Tool '{name}' output:"))
        return {"tools": names, "text": "\n".join(lines)}

    def _skills(
        self,
        prompt: str,
        skills: str | list[str] | tuple[str, ...] | None,
        use_search: bool | None,
        auto_tools: bool | None,
    ) -> list[str]:
        picks: list[str] = []
        if skills is not None:
            raw = [skills] if isinstance(skills, str) else list(skills)
            for item in raw:
                name = str(item).strip().lower()
                if name not in {"search", "extract"}:
                    raise ValueError("unsupported skill. Supported skills are: search, extract")
                if name not in picks:
                    picks.append(name)
            return picks
        if use_search:
            return ["search"]
        enabled = self.cfg.auto_tools if auto_tools is None else auto_tools
        if not enabled or use_search is False:
            return []
        if not self.cfg.auto_search or not self._auto_search(prompt) or not self._search_ready():
            return []
        return ["search"]

    def _ensure_tavily(self) -> None:
        if self.cfg.search_tool in self.tools.names():
            return
        self.use_tavily(api_key=self.cfg.tavily_key, tool=self.cfg.search_tool)

    def _search_ready(self) -> bool:
        if self.cfg.search_tool in self.tools.names():
            return True
        return bool(self.cfg.tavily_key)

    def _skill_tool(self, name: str | None, skill: str) -> Any:
        key = name or self.cfg.search_tool
        tool = self.get_tool(key)
        if not hasattr(tool, skill):
            raise TypeError(f"tool '{key}' does not support {skill}()")
        return tool

    def _urls(self, urls: str | list[str] | tuple[str, ...] | None, prompt: str) -> list[str]:
        if urls is None:
            return self._find_urls(prompt)
        if isinstance(urls, str):
            return [urls]
        return [str(url) for url in urls]

    def _find_urls(self, text: str) -> list[str]:
        out: list[str] = []
        for part in text.split():
            if part.startswith("http://") or part.startswith("https://"):
                out.append(part.rstrip(".,);]"))
        return out

    def _auto_search(self, prompt: str) -> bool:
        text = prompt.strip().lower()
        marks = (
            "latest ",
            "today",
            "current ",
            "news",
            "recent",
            "update",
            "harga",
            "price",
            "release",
            "version",
            "documentation",
            "docs",
            "best ",
            "top ",
            "who is",
            "what happened",
            "find",
            "search",
            "look up",
            "cari",
            "berapa harga",
            "apa kabar terbaru",
        )
        return any(mark in text for mark in marks)

    def _skill_ctx_text(self, items: list[tuple[str, ToolRes]]) -> str:
        lines = ["Skill grounding data:"]
        for name, res in items:
            head = {"search": "Web search findings:", "extract": "Extracted page content:"}[name]
            lines.append(res.as_text(head))
        lines.append("Use this data as factual grounding for the final answer.")
        return "\n".join(lines)

    def _skill_text(self, name: str, res: ToolRes) -> str:
        head = {"search": "Web search findings:", "extract": "Extracted page content:"}[name]
        return res.as_text(head)

    def _other(self, provider: str) -> str:
        return "deepseek" if provider == "flash" else "flash"

    def _can_fallback(self, provider: str, backup: str | None) -> bool:
        if not self.cfg.fallback and not backup:
            return False
        try:
            name = backup or self._other(provider)
            self.provider_map.get(name)
        except MissingProviderError:
            return False
        return name != provider


@dataclass(slots=True)
class Session:
    client: Client
    system: str | None = None
    max_turns: int | None = None
    history: list[tuple[str, str]] = field(default_factory=list)

    def ask(self, prompt: str, **kwargs: Any) -> Res:
        full = self._prompt(prompt)
        res = self.client.flash(full, system=self.system, **kwargs)
        self.history.append(("user", prompt))
        self.history.append(("assistant", res.text))
        self._trim()
        return res

    def flash(self, prompt: str, **kwargs: Any) -> Res:
        return self.ask(prompt, **kwargs)

    def reset(self) -> None:
        self.history.clear()

    def _prompt(self, prompt: str) -> str:
        if not self.history:
            return prompt
        lines = ["Conversation so far:"]
        for role, text in self.history:
            lines.append(f"{role.title()}: {text}")
        lines.append(f"User: {prompt}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def _trim(self) -> None:
        if self.max_turns is None or self.max_turns <= 0:
            return
        size = self.max_turns * 2
        if len(self.history) > size:
            self.history = self.history[-size:]


class AsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._client = Client(*args, **kwargs)

    async def flash(self, prompt: str, **kwargs: Any) -> Res:
        return await asyncio.to_thread(self._client.flash, prompt, **kwargs)

    async def ask(self, prompt: str, **kwargs: Any) -> Res:
        return await self.flash(prompt, **kwargs)

    def add_tool(self, tool: Tool) -> Tool:
        return self._client.add_tool(tool)

    def register_tool(self, tool: Tool) -> Tool:
        return self._client.register_tool(tool)

    def add_fn(self, name: str, fn: Any, *, desc: str = "", fmt: Any = None) -> Tool:
        return self._client.add_fn(name, fn, desc=desc, fmt=fmt)

    def register_function(self, name: str, func: Any, *, description: str = "", formatter: Any = None) -> Tool:
        return self._client.register_function(name, func, description=description, formatter=formatter)

    def list_tools(self) -> tuple[str, ...]:
        return self._client.list_tools()

    def list_providers(self) -> tuple[str, ...]:
        return self._client.list_providers()

    def get_caps(self, provider: str) -> Caps:
        return self._client.get_caps(provider)

    def session(self, *, system: str | None = None, max_turns: int | None = None) -> AsyncSession:
        return AsyncSession(self, system=system, max_turns=max_turns)


@dataclass(slots=True)
class AsyncSession:
    client: AsyncClient
    system: str | None = None
    max_turns: int | None = None
    history: list[tuple[str, str]] = field(default_factory=list)

    async def ask(self, prompt: str, **kwargs: Any) -> Res:
        full = self._prompt(prompt)
        res = await self.client.flash(full, system=self.system, **kwargs)
        self.history.append(("user", prompt))
        self.history.append(("assistant", res.text))
        self._trim()
        return res

    async def flash(self, prompt: str, **kwargs: Any) -> Res:
        return await self.ask(prompt, **kwargs)

    def reset(self) -> None:
        self.history.clear()

    def _prompt(self, prompt: str) -> str:
        if not self.history:
            return prompt
        lines = ["Conversation so far:"]
        for role, text in self.history:
            lines.append(f"{role.title()}: {text}")
        lines.append(f"User: {prompt}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def _trim(self) -> None:
        if self.max_turns is None or self.max_turns <= 0:
            return
        size = self.max_turns * 2
        if len(self.history) > size:
            self.history = self.history[-size:]
