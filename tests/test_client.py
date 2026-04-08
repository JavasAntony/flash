from __future__ import annotations

import pytest

from javaxFlash import (
    Client,
    Config,
    FlashClient,
    FlashConfig,
    JsonSchema,
    ProviderError,
    Schema,
    SchemaValidationError,
    ToolExecutionError,
)
from javaxFlash.tools import ToolResult
from javaxFlash.transport import TransportResult


class FakeTransport:
    def __init__(self, responses: dict[str, list[object]]):
        self.responses = {name: list(items) for name, items in responses.items()}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post_json(self, *, url: str, payload: dict[str, object], provider_name: str) -> TransportResult:
        self.calls.append((provider_name, payload))
        item = self.responses[provider_name].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_result(
    text: str,
    *,
    model: str = "test-model",
    retry_count: int = 0,
    latency_ms: float = 12.5,
) -> TransportResult:
    return TransportResult(
        payload={"text": text, "model": model},
        status_code=200,
        retry_count=retry_count,
        latency_ms=latency_ms,
    )


def test_forced_provider_alias_resolves_to_flash() -> None:
    transport = FakeTransport({"flash": [make_result("hello from flash")], "deepseek": []})
    client = FlashClient(transport=transport)

    response = client.flash("Say hello.", provider="gemini")

    assert response.provider == "flash"
    assert response.text == "hello from flash"
    assert response.route_reason == "provider forced explicitly: flash"


def test_simple_public_aliases_point_to_main_types() -> None:
    assert Client is FlashClient
    assert Config is FlashConfig
    assert JsonSchema is Schema


def test_fallback_uses_secondary_provider_when_primary_fails() -> None:
    transport = FakeTransport(
        {
            "flash": [ProviderError("flash unavailable", provider="flash")],
            "deepseek": [make_result("fallback response", model="deepseek-r1")],
        }
    )
    client = FlashClient(
        config=FlashConfig(fallback_enabled=True),
        transport=transport,
    )

    response = client.flash("What is Python?")

    assert response.provider == "deepseek"
    assert response.text == "fallback response"
    assert "fallback to deepseek" in response.route_reason


def test_structured_output_is_parsed_when_schema_is_provided() -> None:
    transport = FakeTransport(
        {
            "flash": [
                make_result('{"title":"Cleanup auth","priority":"high","action_items":["refactor","test"]}')
            ],
            "deepseek": [],
        }
    )
    client = FlashClient(transport=transport)
    schema = Schema(
        name="task",
        fields={
            "title": str,
            "priority": str,
            "action_items": [str],
        },
    )

    response = client.flash("Plan the work.", provider="flash", schema=schema)

    assert response.structured_output == {
        "title": "Cleanup auth",
        "priority": "high",
        "action_items": ["refactor", "test"],
    }
    provider_name, payload = transport.calls[0]
    assert provider_name == "flash"
    assert "Return the answer as valid JSON matching this schema." in payload["prompt"]


def test_schema_validation_error_is_raised_for_invalid_json_shape() -> None:
    transport = FakeTransport(
        {
            "flash": [make_result('{"title":"Cleanup auth"}')],
            "deepseek": [],
        }
    )
    client = FlashClient(transport=transport)
    schema = Schema(
        name="task",
        fields={
            "title": str,
            "priority": str,
        },
    )

    with pytest.raises(SchemaValidationError):
        client.flash("Plan the work.", provider="flash", schema=schema)


class FakeSearchTool:
    name = "tavily"
    description = "fake search"

    def search(self, query: str, limit: int = 5):
        return ToolResult(
            tool_name=self.name,
            output=[
                {
                    "title": "Python 3.13 Release Notes",
                    "url": "https://example.com/python-313",
                    "content": "Python 3.13 improves startup performance and error messages.",
                    "published_date": "2024-10-07",
                    "score": 0.98,
                }
            ],
            metadata={
                "answer": "Python 3.13 includes interpreter and error-message improvements.",
                "query": query,
            },
        )

    def extract(self, url: str):
        return ToolResult(
            tool_name=self.name,
            output=[
                {
                    "title": "Python docs",
                    "url": url,
                    "content": "The docs explain retries and recommended patterns.",
                }
            ],
        )

    def crawl(self, url: str, instructions: str | None = None):
        return ToolResult(
            tool_name=self.name,
            output=[
                {
                    "title": "Docs page",
                    "url": url,
                    "content": f"Crawled content with instructions: {instructions or 'none'}",
                }
            ],
        )


def test_auto_search_adds_curated_search_context_to_prompt() -> None:
    transport = FakeTransport({"flash": [make_result("fresh answer")], "deepseek": []})
    client = FlashClient(
        config=FlashConfig(auto_search=True, tavily_api_key="test-key"),
        transport=transport,
    )
    client.register_tool(FakeSearchTool())

    response = client.flash("What is the latest Python release?")

    assert response.search_used is True
    assert response.search_query == "What is the latest Python release?"
    _, payload = transport.calls[0]
    assert "Skill grounding data:" in payload["prompt"]
    assert "Python 3.13 Release Notes" in payload["prompt"]
    assert "https://example.com/python-313" in payload["prompt"]


def test_explicit_search_can_be_enabled_per_request() -> None:
    transport = FakeTransport({"flash": [make_result("answer")], "deepseek": []})
    client = FlashClient(
        config=FlashConfig(auto_search=False, tavily_api_key="test-key"),
        transport=transport,
    )
    client.register_tool(FakeSearchTool())

    response = client.flash("Explain retries", use_search=True, search_query="retry best practices")

    assert response.search_used is True
    assert response.search_query == "retry best practices"


def test_manual_skills_are_injected_into_prompt_without_returning_tool_result() -> None:
    transport = FakeTransport({"flash": [make_result("final ai answer")], "deepseek": []})
    client = FlashClient(
        config=FlashConfig(search_tool_name="tavily", tavily_api_key="test-key"),
        transport=transport,
    )
    client.register_tool(FakeSearchTool())

    response = client.flash(
        "Use docs https://docs.example.com/retries",
        skills=["search", "extract"],
        search_query="retry best practices",
    )

    assert response.text == "final ai answer"
    assert response.skills_used == ("search", "extract")
    _, payload = transport.calls[0]
    assert "Web search findings:" in payload["prompt"]
    assert "Extracted page content:" in payload["prompt"]
    assert "ToolResult(" not in payload["prompt"]


def test_manual_crawl_skill_is_injected_into_prompt() -> None:
    transport = FakeTransport({"flash": [make_result("final ai answer")], "deepseek": []})
    client = FlashClient(
        config=FlashConfig(search_tool_name="tavily", tavily_api_key="test-key"),
        transport=transport,
    )
    client.register_tool(FakeSearchTool())

    response = client.flash(
        "Crawl docs from https://docs.example.com/retries",
        skills=["crawl"],
        crawl_instructions="Focus on retry recommendations",
    )

    assert response.skills_used == ("crawl",)
    _, payload = transport.calls[0]
    assert "Crawled site content:" in payload["prompt"]
    assert "Focus on retry recommendations" in payload["prompt"]


def test_manual_extract_without_url_raises_clear_error() -> None:
    client = FlashClient(config=FlashConfig(search_tool_name="tavily", tavily_api_key="test-key"))
    client.register_tool(FakeSearchTool())

    with pytest.raises(ValueError):
        client.flash("Summarize this page", skills=["extract"])


def test_manual_search_surfaces_tool_errors_cleanly() -> None:
    class BrokenSearchTool:
        name = "tavily"
        description = "broken search"

        def search(self, query: str, limit: int = 5):
            raise ToolExecutionError("search backend unavailable")

    client = FlashClient(config=FlashConfig(search_tool_name="tavily", tavily_api_key="test-key"))
    client.register_tool(BrokenSearchTool())

    with pytest.raises(ToolExecutionError):
        client.flash("What is the latest Python release?", skills="search")
