from __future__ import annotations

from typing import Any

from .config import FlashConfig, normalize_provider_name
from .errors import ProviderError, ProviderNotFoundError
from .models import FlashRequest, FlashResponse
from .providers import DeepSeekProvider, FlashProvider, ProviderRegistry
from .router import FlashRouter
from .schema import SchemaLike, parse_structured_output, schema_instruction_block
from .tools import BaseTool, TavilyTool, ToolRegistry, ToolResult
from .transport import HttpTransport


class FlashClient:
    def __init__(
        self,
        config: FlashConfig | None = None,
        *,
        router: FlashRouter | None = None,
        transport: HttpTransport | None = None,
        providers: list | tuple | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.config = config or FlashConfig()
        self.transport = transport or HttpTransport(self.config)
        self.router = router or FlashRouter()
        self.tool_registry = tool_registry or ToolRegistry()
        self.provider_registry = ProviderRegistry(
            providers
            or (
                FlashProvider(self.config, self.transport),
                DeepSeekProvider(self.config, self.transport),
            )
        )
        self.providers = self.provider_registry.providers

    def flash(
        self,
        prompt: str,
        *,
        mode: str | None = None,
        provider: str | None = None,
        auto_route: bool | None = None,
        system_instruction: str | None = None,
        fallback_provider: str | None = None,
        model: str | None = None,
        schema: SchemaLike | None = None,
        include_raw: bool | None = None,
        skills: str | list[str] | tuple[str, ...] | None = None,
        use_search: bool | None = None,
        search_query: str | None = None,
        skill_urls: str | list[str] | tuple[str, ...] | None = None,
        crawl_instructions: str | None = None,
        **kwargs: Any,
    ) -> FlashResponse:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")

        auto_route = self.config.auto_route if auto_route is None else auto_route
        requested_provider = normalize_provider_name(provider) if provider else None
        fallback_provider = self._resolve_fallback_provider(fallback_provider)
        decision = self.router.choose(
            prompt=prompt,
            mode=mode,
            forced_provider=requested_provider,
            auto_route=auto_route,
            default_provider=self.config.default_provider,
        )

        request = FlashRequest(
            prompt=prompt,
            system_instruction=self._build_system_instruction(system_instruction, schema),
            model=model,
            include_raw=self.config.capture_raw_response if include_raw is None else include_raw,
            schema=schema,
            options=dict(kwargs),
        )
        skill_bundle = self._maybe_prepare_skill_context(
            prompt=prompt,
            skills=skills,
            use_search=use_search,
            search_query=search_query,
            skill_urls=skill_urls,
            crawl_instructions=crawl_instructions,
        )
        request.prompt = self._build_prompt(prompt, schema, skill_bundle)

        try:
            response = self.provider_registry.get(decision.provider).generate(request)
        except ProviderError as exc:
            if not self._should_fallback(decision.provider, fallback_provider):
                raise
            response = self._run_fallback(
                prompt_request=request,
                primary_provider=decision.provider,
                fallback_provider=fallback_provider or self._other_provider(decision.provider),
                primary_error=exc,
                route_reason=decision.reason,
            )
        else:
            response.route_reason = decision.reason

        if schema is not None:
            response.structured_output = parse_structured_output(response.text, schema)
        if skill_bundle is not None:
            response.skills_used = tuple(skill_bundle["skills"])
            response.skills_summary = skill_bundle["summary"]
        if skill_bundle is not None and "search" in skill_bundle["skills"]:
            response.search_used = True
            response.search_query = skill_bundle.get("search_query")
            response.search_summary = skill_bundle["summary"]

        return response

    def ask(self, prompt: str, **kwargs: Any) -> FlashResponse:
        return self.flash(prompt, **kwargs)

    def register_tool(self, tool: BaseTool) -> BaseTool:
        self.tool_registry.register(tool)
        return tool

    def add_tool(self, tool: BaseTool) -> BaseTool:
        return self.register_tool(tool)

    def get_tool(self, name: str) -> BaseTool:
        return self.tool_registry.get(name)

    def list_tools(self) -> tuple[str, ...]:
        return self.tool_registry.names()

    def run_tool(self, name: str, **kwargs: Any) -> Any:
        return self.tool_registry.run(name, **kwargs)

    def search(self, query: str, *, limit: int = 5, tool_name: str | None = None) -> str:
        return self._render_skill_result(
            "search",
            self._get_skill_tool(tool_name, "search").search(query=query, limit=limit),
        )

    def extract(self, url: str, *, tool_name: str | None = None) -> str:
        return self._render_skill_result(
            "extract",
            self._get_skill_tool(tool_name, "extract").extract(url),
        )

    def crawl(self, url: str, *, instructions: str | None = None, tool_name: str | None = None) -> str:
        return self._render_skill_result(
            "crawl",
            self._get_skill_tool(tool_name, "crawl").crawl(url, instructions=instructions),
        )

    def use_tavily(
        self,
        api_key: str | None = None,
        *,
        tool_name: str = "tavily",
        topic: str = "general",
        search_depth: str = "basic",
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> BaseTool:
        tool = TavilyTool(
            api_key=api_key or self.config.tavily_api_key,
            topic=topic,
            search_depth=search_depth,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        tool.name = tool_name
        return self.register_tool(tool)

    def _run_fallback(
        self,
        *,
        prompt_request: FlashRequest,
        primary_provider: str,
        fallback_provider: str,
        primary_error: ProviderError,
        route_reason: str,
    ) -> FlashResponse:
        try:
            response = self.provider_registry.get(fallback_provider).generate(prompt_request)
        except ProviderError as fallback_error:
            raise ProviderError(
                (
                    f"{primary_provider} failed: {primary_error}. "
                    f"Fallback provider {fallback_provider} also failed: {fallback_error}"
                ),
                provider=fallback_provider,
            ) from fallback_error

        response.route_reason = (
            f"{route_reason}; fallback to {fallback_provider} after {primary_provider} failed"
        )
        return response

    def _resolve_fallback_provider(self, fallback_provider: str | None) -> str | None:
        resolved = fallback_provider or self.config.fallback_provider
        if not resolved:
            return None
        return normalize_provider_name(resolved)

    def _build_prompt(
        self,
        prompt: str,
        schema: SchemaLike | None,
        skill_bundle: dict[str, Any] | None,
    ) -> str:
        sections = [prompt.rstrip()]
        if skill_bundle is not None:
            sections.append(
                "\n".join(
                    [
                        "Use the following skill-derived grounding as factual context when answering.",
                        "Rely on this context where relevant, but keep the final answer natural and concise.",
                        skill_bundle["summary"],
                    ]
                )
            )
        if schema is not None:
            sections.append(schema_instruction_block(schema))
        return "\n\n".join(section for section in sections if section)

    def _build_system_instruction(
        self,
        system_instruction: str | None,
        schema: SchemaLike | None,
    ) -> str:
        instruction = system_instruction or self.config.default_system_instruction
        if schema is None:
            return instruction
        return (
            f"{instruction.rstrip()}\n"
            "Return only valid JSON with no markdown fences or extra commentary."
        )

    def _maybe_prepare_skill_context(
        self,
        *,
        prompt: str,
        skills: str | list[str] | tuple[str, ...] | None,
        use_search: bool | None,
        search_query: str | None,
        skill_urls: str | list[str] | tuple[str, ...] | None,
        crawl_instructions: str | None,
    ) -> dict[str, Any] | None:
        selected_skills = self._resolve_requested_skills(prompt, skills, use_search)
        if not selected_skills:
            return None
        self._ensure_tavily_tool()
        tool = self._get_skill_tool(None, "search")
        urls = self._normalize_skill_urls(skill_urls, prompt)
        if any(skill in selected_skills for skill in ("extract", "crawl")) and not urls:
            raise ValueError(
                "extract and crawl skills require at least one URL in skill_urls or the prompt"
            )
        results: list[tuple[str, ToolResult]] = []

        for skill in selected_skills:
            if skill == "search":
                query = search_query or prompt
                results.append((skill, tool.search(query=query, limit=self.config.search_max_results)))
                continue
            if skill == "extract":
                tool = self._get_skill_tool(None, "extract")
                for url in urls:
                    results.append((skill, tool.extract(url)))
                continue
            if skill == "crawl":
                tool = self._get_skill_tool(None, "crawl")
                for url in urls:
                    results.append((skill, tool.crawl(url, instructions=crawl_instructions)))
                continue

        if not results:
            return None

        summary = self._format_skill_context(results)
        bundle: dict[str, Any] = {
            "skills": selected_skills,
            "summary": summary,
        }
        if "search" in selected_skills:
            bundle["search_query"] = search_query or prompt
        return bundle

    def _resolve_requested_skills(
        self,
        prompt: str,
        skills: str | list[str] | tuple[str, ...] | None,
        use_search: bool | None,
    ) -> list[str]:
        selected: list[str] = []
        if skills is not None:
            raw_skills = [skills] if isinstance(skills, str) else list(skills)
            for skill in raw_skills:
                normalized = str(skill).strip().lower()
                if normalized not in {"search", "extract", "crawl"}:
                    raise ValueError(
                        "unsupported skill. Supported skills are: search, extract, crawl"
                    )
                if normalized not in selected:
                    selected.append(normalized)
            return selected

        auto_detected = self._should_auto_search(prompt)
        should_search = self.config.auto_search if use_search is None else use_search
        if not should_search and not auto_detected:
            return []
        if not should_search and auto_detected:
            if not self._search_is_configured():
                return []
            should_search = True
        if not should_search:
            return []
        return ["search"]

    def _ensure_tavily_tool(self) -> None:
        if self.config.search_tool_name in self.tool_registry.names():
            return
        self.use_tavily(
            api_key=self.config.tavily_api_key,
            tool_name=self.config.search_tool_name,
        )

    def _search_is_configured(self) -> bool:
        if self.config.search_tool_name in self.tool_registry.names():
            return True
        return bool(self.config.tavily_api_key)

    def _get_skill_tool(self, tool_name: str | None, skill_name: str) -> Any:
        resolved_name = tool_name or self.config.search_tool_name
        tool = self.get_tool(resolved_name)
        if not hasattr(tool, skill_name):
            raise TypeError(f"tool '{resolved_name}' does not support {skill_name}()")
        return tool

    def _normalize_skill_urls(
        self,
        skill_urls: str | list[str] | tuple[str, ...] | None,
        prompt: str,
    ) -> list[str]:
        if skill_urls is None:
            return self._extract_urls_from_text(prompt)
        if isinstance(skill_urls, str):
            return [skill_urls]
        return [str(url) for url in skill_urls]

    def _extract_urls_from_text(self, text: str) -> list[str]:
        urls: list[str] = []
        for chunk in text.split():
            if chunk.startswith("http://") or chunk.startswith("https://"):
                urls.append(chunk.rstrip(".,);]"))
        return urls

    def _should_auto_search(self, prompt: str) -> bool:
        normalized = prompt.strip().lower()
        web_markers = (
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
        )
        question_markers = (
            "who is",
            "what happened",
            "find",
            "search",
            "look up",
            "cari",
            "berapa harga",
            "apa kabar terbaru",
        )
        return any(marker in normalized for marker in web_markers + question_markers)

    def _format_skill_context(self, results: list[tuple[str, ToolResult]]) -> str:
        lines = ["Skill grounding data:"]
        for skill_name, result in results:
            heading = {
                "search": "Web search findings:",
                "extract": "Extracted page content:",
                "crawl": "Crawled site content:",
            }[skill_name]
            lines.append(result.as_prompt_context(heading))
        lines.append("Use this data as factual grounding for the final answer.")
        return "\n".join(lines)

    def _render_skill_result(self, skill_name: str, result: ToolResult) -> str:
        heading = {
            "search": "Web search findings:",
            "extract": "Extracted page content:",
            "crawl": "Crawled site content:",
        }[skill_name]
        return result.as_prompt_context(heading)

    def _other_provider(self, provider: str) -> str:
        return "deepseek" if provider == "flash" else "flash"

    def _should_fallback(self, provider: str, fallback_provider: str | None) -> bool:
        if not self.config.fallback_enabled and not fallback_provider:
            return False
        try:
            candidate = fallback_provider or self._other_provider(provider)
            self.provider_registry.get(candidate)
        except ProviderNotFoundError:
            return False
        return candidate != provider


AIClient = FlashClient
