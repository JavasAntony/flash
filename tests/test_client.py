from __future__ import annotations

import asyncio

import pytest

from javaxFlash import AsyncClient, Client, Config, ProviderError, Schema, SchemaError, ToolError
from javaxFlash.tools import ToolRes
from javaxFlash.transport import NetRes


class FakeNet:
    def __init__(self, data: dict[str, list[object]]):
        self.data = {name: list(items) for name, items in data.items()}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post(self, *, url: str, data: dict[str, object], provider: str) -> NetRes:
        self.calls.append((provider, data))
        item = self.data[provider].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def net_res(
    text: str,
    *,
    model: str = "test-model",
    retries: int = 0,
    latency: float = 12.5,
) -> NetRes:
    return NetRes(data={"text": text, "model": model}, status=200, retries=retries, latency=latency)


def test_forced_provider_alias_resolves_to_flash() -> None:
    net = FakeNet({"flash": [net_res("hello from flash")], "deepseek": []})
    client = Client(net=net)

    res = client.flash("Say hello.", provider="gemini")

    assert res.provider == "flash"
    assert res.text == "hello from flash"
    assert res.reason == "provider forced explicitly: flash"


def test_fallback_uses_secondary_provider_when_primary_fails() -> None:
    net = FakeNet(
        {
            "flash": [ProviderError("flash unavailable", provider="flash")],
            "deepseek": [net_res("fallback response", model="deepseek-r1")],
        }
    )
    client = Client(cfg=Config(fallback=True), net=net)

    res = client.flash("What is Python?")

    assert res.provider == "deepseek"
    assert res.text == "fallback response"
    assert "fallback to deepseek" in res.reason


def test_structured_output_is_parsed_when_schema_is_provided() -> None:
    net = FakeNet({"flash": [net_res('{"title":"Cleanup auth","priority":"high","items":["refactor","test"]}')], "deepseek": []})
    client = Client(net=net)
    schema = Schema(name="task", fields={"title": str, "priority": str, "items": [str]})

    res = client.flash("Plan the work.", provider="flash", schema=schema)

    assert res.data == {"title": "Cleanup auth", "priority": "high", "items": ["refactor", "test"]}
    provider, payload = net.calls[0]
    assert provider == "flash"
    assert "Return the answer as valid JSON matching this schema." in payload["prompt"]


def test_schema_error_is_raised_for_invalid_json_shape() -> None:
    net = FakeNet({"flash": [net_res('{"title":"Cleanup auth"}')], "deepseek": []})
    client = Client(net=net)
    schema = Schema(name="task", fields={"title": str, "priority": str})

    with pytest.raises(SchemaError):
        client.flash("Plan the work.", provider="flash", schema=schema)


class FakeSearch:
    name = "tavily"
    desc = "fake search"

    def search(self, query: str, limit: int = 5):
        return ToolRes(
            name=self.name,
            items=[{"title": "Python 3.13 Release Notes", "url": "https://example.com/python-313", "content": "Python 3.13 improves startup performance and error messages."}],
            meta={"answer": "Python 3.13 includes interpreter and error-message improvements.", "query": query},
        )

    def extract(self, url: str):
        return ToolRes(name=self.name, items=[{"title": "Python docs", "url": url, "content": "The docs explain retries and recommended patterns."}])


def test_search_is_not_auto_injected_by_default_even_when_auto_search_is_enabled() -> None:
    net = FakeNet({"flash": [net_res("fresh answer")], "deepseek": []})
    client = Client(cfg=Config(auto_search=True, tavily_key="test-key"), net=net)
    client.register_tool(FakeSearch())

    res = client.flash("What is the latest Python release?")

    assert res.searched is False
    assert res.search_query is None
    _, payload = net.calls[0]
    assert "Skill grounding data:" not in payload["prompt"]


def test_auto_tools_can_be_enabled_explicitly_for_legacy_behavior() -> None:
    net = FakeNet({"flash": [net_res("fresh answer")], "deepseek": []})
    client = Client(cfg=Config(auto_search=True, auto_tools=True, tavily_key="test-key"), net=net)
    client.register_tool(FakeSearch())

    res = client.flash("What is the latest Python release?")

    assert res.searched is True
    assert res.search_query == "What is the latest Python release?"
    _, payload = net.calls[0]
    assert "Skill grounding data:" in payload["prompt"]


def test_explicit_search_can_be_enabled_per_request() -> None:
    net = FakeNet({"flash": [net_res("answer")], "deepseek": []})
    client = Client(cfg=Config(auto_search=False, tavily_key="test-key"), net=net)
    client.register_tool(FakeSearch())

    res = client.flash("Explain retries", use_search=True, search_query="retry best practices")

    assert res.searched is True
    assert res.search_query == "retry best practices"


def test_manual_skills_are_injected_into_prompt_without_returning_tool_result() -> None:
    net = FakeNet({"flash": [net_res("final ai answer")], "deepseek": []})
    client = Client(cfg=Config(search_tool="tavily", tavily_key="test-key"), net=net)
    client.register_tool(FakeSearch())

    res = client.flash("Use docs https://docs.example.com/retries", skills=["search", "extract"], search_query="retry best practices")

    assert res.text == "final ai answer"
    assert res.skills == ("search", "extract")
    _, payload = net.calls[0]
    assert "Web search findings:" in payload["prompt"]
    assert "Extracted page content:" in payload["prompt"]


def test_manual_extract_without_url_raises_clear_error() -> None:
    client = Client(cfg=Config(search_tool="tavily", tavily_key="test-key"))
    client.register_tool(FakeSearch())

    with pytest.raises(ValueError):
        client.flash("Summarize this page", skills=["extract"])


def test_manual_search_surfaces_tool_errors_cleanly() -> None:
    class BrokenSearch:
        name = "tavily"
        desc = "broken search"

        def search(self, query: str, limit: int = 5):
            raise ToolError("search backend unavailable")

    client = Client(cfg=Config(search_tool="tavily", tavily_key="test-key"))
    client.register_tool(BrokenSearch())

    with pytest.raises(ToolError):
        client.flash("What is the latest Python release?", skills="search")


def test_local_function_tool_results_are_injected_into_prompt() -> None:
    net = FakeNet({"flash": [net_res("answer with local tool")], "deepseek": []})
    client = Client(net=net)
    client.add_fn("project_info", lambda: {"title": "Project", "content": "The library focuses on multi-provider routing."})

    res = client.flash("Summarize the current project focus.", tool_calls={"project_info": {}})

    assert res.tools == ("project_info",)
    _, payload = net.calls[0]
    assert "Local tool results:" in payload["prompt"]


def test_session_keeps_conversation_history_between_calls() -> None:
    net = FakeNet({"flash": [net_res("First answer"), net_res("Second answer")], "deepseek": []})
    client = Client(net=net)
    session = client.session()

    session.ask("My name is Javas.")
    session.ask("What is my name?")

    _, payload = net.calls[1]
    assert "Conversation so far:" in payload["prompt"]
    assert "User: My name is Javas." in payload["prompt"]


def test_hooks_receive_request_response_and_tool_events() -> None:
    events: list[tuple[str, dict[str, object]]] = []
    net = FakeNet({"flash": [net_res("hooked")], "deepseek": []})
    client = Client(cfg=Config(hooks=(lambda event, data: events.append((event, data)),)), net=net)
    client.add_fn("echo_tool", lambda text: {"content": text})

    client.flash("Echo this tool output.", tool_calls={"echo_tool": {"text": "hi"}})

    names = [event for event, _ in events]
    assert "flash_requested" in names
    assert "tool_called" in names
    assert "response_received" in names


def test_async_client_wraps_sync_flash_client() -> None:
    net = FakeNet({"flash": [net_res("async hello")], "deepseek": []})
    client = AsyncClient(net=net)

    res = asyncio.run(client.flash("Say hello."))

    assert res.text == "async hello"
    assert res.provider == "flash"


def test_caps_are_exposed_on_client_and_response() -> None:
    net = FakeNet({"flash": [net_res("hello")], "deepseek": []})
    client = Client(net=net)

    res = client.flash("Say hello.")
    caps = client.get_caps("flash")

    assert res.caps == caps
    assert caps.schema is True


def test_deepseek_thinking_tags_are_parsed_cleanly() -> None:
    net = FakeNet(
        {
            "flash": [],
            "deepseek": [
                NetRes(
                    data={"text": "<thinking>internal chain of thought</thinking>Clean final answer."},
                    status=200,
                    retries=0,
                    latency=5.0,
                )
            ],
        }
    )
    client = Client(net=net)

    res = client.flash("Analyze this deeply.", provider="deepseek")

    assert res.text == "Clean final answer."
    assert res.think == "internal chain of thought"
