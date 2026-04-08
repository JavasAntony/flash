from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import os
from typing import Any, Callable

from .errors import ToolExecutionError

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None  # type: ignore[assignment]


@dataclass(slots=True)
class ToolResult:
    tool_name: str
    output: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_prompt_context(self, heading: str) -> str:
        lines = [heading]
        answer = str(self.metadata.get("answer") or "").strip()
        if answer:
            lines.append(f"Overview: {answer}")
        for index, item in enumerate(self.output, start=1):
            title = str(item.get("title", "")).strip() or f"Item {index}"
            url = str(item.get("url", "")).strip()
            content = str(item.get("content", "")).strip()
            lines.append(f"{index}. {title}")
            if url:
                lines.append(f"   URL: {url}")
            if content:
                lines.append(f"   Content: {content}")
        return "\n".join(lines)


class BaseTool(ABC):
    name: str
    description: str = ""

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


class TavilyTool(BaseTool):
    name = "tavily"
    description = "Tavily-backed support tool for search, extract, and crawl."
    supported_skills = ("search", "extract", "crawl")

    def __init__(
        self,
        api_key: str | None = None,
        *,
        tavily_client: Any | None = None,
        topic: str = "general",
        search_depth: str = "basic",
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.topic = topic
        self.search_depth = search_depth
        self.include_answer = include_answer
        self.include_raw_content = include_raw_content
        self._client = tavily_client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def search(self, query: str, limit: int = 5) -> ToolResult:
        return self._invoke(
            tool_name="search",
            method=self.client.search,
            normalizer=self._normalize_search,
            query=query,
            max_results=limit,
            topic=self.topic,
            search_depth=self.search_depth,
            include_answer=self.include_answer,
            include_raw_content=self.include_raw_content,
        )

    def extract(self, url: str) -> ToolResult:
        return self._invoke(
            tool_name="extract",
            method=self.client.extract,
            normalizer=self._normalize_extract,
            urls=[url],
            include_images=False,
        )

    def crawl(self, url: str, instructions: str | None = None) -> ToolResult:
        payload: dict[str, Any] = {"url": url}
        if instructions:
            payload["instructions"] = instructions
        return self._invoke(
            tool_name="crawl",
            method=self.client.crawl,
            normalizer=self._normalize_crawl,
            **payload,
        )

    def run(self, **kwargs: Any) -> ToolResult:
        skill = str(kwargs.get("skill", "search")).strip().lower()
        if skill == "search":
            query = str(kwargs.get("query") or "").strip()
            if not query:
                raise ToolExecutionError("search skill requires a non-empty query")
            return self.search(query=query, limit=int(kwargs.get("limit", 5)))
        if skill == "extract":
            url = str(kwargs.get("url") or "").strip()
            if not url:
                raise ToolExecutionError("extract skill requires a URL")
            return self.extract(url)
        if skill == "crawl":
            url = str(kwargs.get("url") or "").strip()
            if not url:
                raise ToolExecutionError("crawl skill requires a URL")
            return self.crawl(url, instructions=kwargs.get("instructions"))
        raise ToolExecutionError(
            f"unsupported Tavily skill '{skill}'. Supported skills: {', '.join(self.supported_skills)}"
        )

    def _build_client(self) -> Any:
        if TavilyClient is None:
            raise ToolExecutionError(
                "Tavily support requires the 'tavily-python' package. Install it with 'pip install tavily-python'."
            )
        if not self.api_key:
            raise ToolExecutionError(
                "Tavily requires an API key. Set TAVILY_API_KEY or pass api_key."
            )
        return TavilyClient(api_key=self.api_key)

    def _invoke(
        self,
        tool_name: str,
        method: Callable[..., Any],
        normalizer: Callable[[Any], ToolResult],
        **kwargs: Any,
    ) -> ToolResult:
        try:
            response = method(**kwargs)
        except Exception as exc:
            raise ToolExecutionError(f"tavily {tool_name} failed: {exc}") from exc
        return normalizer(response)

    def _normalize_search(self, payload: Any) -> ToolResult:
        data = self._as_dict(payload)
        return ToolResult(
            tool_name="search",
            output=self._collect_items(data.get("results", []), content_keys=("content", "raw_content")),
            metadata={
                "query": data.get("query"),
                "answer": data.get("answer"),
                "response_time": data.get("response_time"),
            },
        )

    def _normalize_extract(self, payload: Any) -> ToolResult:
        data = self._as_dict(payload)
        return ToolResult(
            tool_name="extract",
            output=self._collect_items(data.get("results", []), content_keys=("raw_content", "content")),
            metadata={
                "response_time": data.get("response_time"),
                "failed_results": data.get("failed_results", []),
            },
        )

    def _normalize_crawl(self, payload: Any) -> ToolResult:
        data = self._as_dict(payload)
        return ToolResult(
            tool_name="crawl",
            output=self._collect_items(data.get("results", []), content_keys=("raw_content", "content")),
            metadata={
                "base_url": data.get("base_url"),
                "response_time": data.get("response_time"),
            },
        )

    def _collect_items(
        self,
        results: Any,
        *,
        content_keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        if not isinstance(results, list):
            return output
        for item in results:
            if not isinstance(item, dict):
                continue
            content = ""
            for key in content_keys:
                value = str(item.get(key, "")).strip()
                if value:
                    content = self._trim_text(value)
                    break
            output.append(
                {
                    "title": item.get("title", item.get("url", "")),
                    "url": item.get("url", ""),
                    "content": content,
                }
            )
        return output

    def _as_dict(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        raise ToolExecutionError("Tavily client returned an unexpected payload type")

    def _trim_text(self, value: Any, limit: int = 280) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not getattr(tool, "name", "").strip():
            raise ToolExecutionError("tools must define a non-empty name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolExecutionError(f"tool '{name}' is not registered") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def run(self, name: str, **kwargs: Any) -> ToolResult:
        return self.get(name).run(**kwargs)


Tool = BaseTool
