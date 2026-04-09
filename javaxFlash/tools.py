from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import os
from typing import Any, Callable

from .errors import ToolError

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None  # type: ignore[assignment]


@dataclass(slots=True)
class ToolRes:
    name: str
    items: list[dict[str, Any]]
    meta: dict[str, Any] = field(default_factory=dict)

    def as_text(self, head: str) -> str:
        lines = [head]
        note = str(self.meta.get("answer") or "").strip()
        if note:
            lines.append(f"Overview: {note}")
        for i, item in enumerate(self.items, start=1):
            title = str(item.get("title", "")).strip() or f"Item {i}"
            url = str(item.get("url", "")).strip()
            text = str(item.get("content", "")).strip()
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   URL: {url}")
            if text:
                lines.append(f"   Content: {text}")
        return "\n".join(lines)


class Tool(ABC):
    name: str
    desc: str = ""

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolRes:
        raise NotImplementedError


class FuncTool(Tool):
    def __init__(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        desc: str = "",
        fmt: Callable[[Any], list[dict[str, Any]]] | None = None,
    ) -> None:
        key = str(name).strip()
        if not key:
            raise ToolError("function tools must define a non-empty name")
        self.name = key
        self.desc = desc or f"Local callable tool '{key}'."
        self.fn = fn
        self.fmt = fmt

    def run(self, **kwargs: Any) -> ToolRes:
        try:
            value = self.fn(**kwargs)
        except Exception as err:
            raise ToolError(f"tool '{self.name}' failed: {err}") from err
        return ToolRes(name=self.name, items=self._items(value), meta={"kind": "function"})

    def _items(self, value: Any) -> list[dict[str, Any]]:
        if self.fmt is not None:
            return self.fmt(value)
        if isinstance(value, ToolRes):
            return value.items
        if isinstance(value, list):
            out: list[dict[str, Any]] = []
            for i, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    out.append(item)
                else:
                    out.append({"title": f"Item {i}", "content": str(item)})
            return out
        if isinstance(value, dict):
            return [value]
        return [{"title": self.name, "content": str(value)}]


class Tavily(Tool):
    name = "tavily"
    desc = "Tavily-backed support tool for search and extract."
    skills = ("search", "extract")

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        topic: str = "general",
        depth: str = "basic",
        answer: bool = True,
        raw: bool = False,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.topic = topic
        self.depth = depth
        self.answer = answer
        self.raw = raw
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._build()
        return self._client

    def search(self, query: str, limit: int = 5) -> ToolRes:
        return self._call(
            name="search",
            fn=self.client.search,
            fmt=self._search_res,
            query=query,
            max_results=limit,
            topic=self.topic,
            search_depth=self.depth,
            include_answer=self.answer,
            include_raw_content=self.raw,
        )

    def extract(self, url: str) -> ToolRes:
        return self._call(
            name="extract",
            fn=self.client.extract,
            fmt=self._extract_res,
            urls=[url],
            include_images=False,
        )

    def run(self, **kwargs: Any) -> ToolRes:
        skill = str(kwargs.get("skill", "search")).strip().lower()
        if skill == "search":
            query = str(kwargs.get("query") or "").strip()
            if not query:
                raise ToolError("search skill requires a non-empty query")
            return self.search(query=query, limit=int(kwargs.get("limit", 5)))
        if skill == "extract":
            url = str(kwargs.get("url") or "").strip()
            if not url:
                raise ToolError("extract skill requires a URL")
            return self.extract(url)
        raise ToolError(f"unsupported Tavily skill '{skill}'. Supported skills: {', '.join(self.skills)}")

    def _build(self) -> Any:
        if TavilyClient is None:
            raise ToolError("Tavily support requires the 'tavily-python' package. Install it with 'pip install tavily-python'.")
        if not self.api_key:
            raise ToolError("Tavily requires an API key. Set TAVILY_API_KEY or pass api_key.")
        return TavilyClient(api_key=self.api_key)

    def _call(
        self,
        *,
        name: str,
        fn: Callable[..., Any],
        fmt: Callable[[Any], ToolRes],
        **kwargs: Any,
    ) -> ToolRes:
        try:
            data = fn(**kwargs)
        except Exception as err:
            raise ToolError(f"tavily {name} failed: {err}") from err
        return fmt(data)

    def _search_res(self, data: Any) -> ToolRes:
        body = self._dict(data)
        return ToolRes(
            name="search",
            items=self._items(body.get("results", []), keys=("content", "raw_content")),
            meta={
                "query": body.get("query"),
                "answer": body.get("answer"),
                "response_time": body.get("response_time"),
            },
        )

    def _extract_res(self, data: Any) -> ToolRes:
        body = self._dict(data)
        return ToolRes(
            name="extract",
            items=self._items(body.get("results", []), keys=("raw_content", "content")),
            meta={
                "response_time": body.get("response_time"),
                "failed_results": body.get("failed_results", []),
            },
        )

    def _items(self, data: Any, *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(data, list):
            return out
        for item in data:
            if not isinstance(item, dict):
                continue
            text = ""
            for key in keys:
                value = str(item.get(key, "")).strip()
                if value:
                    text = self._trim(value)
                    break
            out.append(
                {
                    "title": item.get("title", item.get("url", "")),
                    "url": item.get("url", ""),
                    "content": text,
                }
            )
        return out

    def _dict(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            return data
        raise ToolError("Tavily client returned an unexpected payload type")

    def _trim(self, value: Any, limit: int = 280) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."


class ToolMap:
    def __init__(self) -> None:
        self.items: dict[str, Tool] = {}

    def add(self, tool: Tool) -> None:
        if not getattr(tool, "name", "").strip():
            raise ToolError("tools must define a non-empty name")
        self.items[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self.items[name]
        except KeyError as err:
            raise ToolError(f"tool '{name}' is not registered") from err

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.items))

    def run(self, name: str, **kwargs: Any) -> ToolRes:
        return self.get(name).run(**kwargs)
