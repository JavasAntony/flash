from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest
import requests

from javaxFlash import FlashConfig, RetryExhaustedError, TavilyTool, ToolExecutionError
from javaxFlash.schema import parse_structured_output
from javaxFlash.transport import HttpTransport


class DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, object], text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> dict[str, object]:
        return self._payload


def test_transport_retries_once_on_rate_limit_then_succeeds() -> None:
    session = Mock()
    session.post.side_effect = [
        DummyResponse(429, {"error": "slow down"}, text="slow down"),
        DummyResponse(200, {"text": "ok", "model": "flash"}),
    ]
    delays: list[float] = []
    transport = HttpTransport(
        FlashConfig(max_retries=2, backoff_base=0.5, jitter=0.0),
        session=session,
        sleeper=delays.append,
        random_fn=lambda start, end: 0.0,
    )

    result = transport.post_json(
        url="https://example.com",
        payload={"prompt": "hello"},
        provider_name="flash",
    )

    assert result.retry_count == 1
    assert delays == [0.5]


def test_transport_raises_retry_exhausted_after_repeated_timeouts() -> None:
    session = Mock()
    session.post.side_effect = requests.Timeout("network timeout")
    transport = HttpTransport(
        FlashConfig(max_retries=2, jitter=0.0),
        session=session,
        sleeper=lambda _: None,
        random_fn=lambda start, end: 0.0,
    )

    with pytest.raises(RetryExhaustedError) as exc:
        transport.post_json(
            url="https://example.com",
            payload={"prompt": "hello"},
            provider_name="flash",
        )

    assert exc.value.attempts == 3


@dataclass
class TicketSummary:
    title: str
    priority: str


def test_parse_structured_output_supports_dataclass_schemas() -> None:
    result = parse_structured_output(
        '{"title":"Refactor router","priority":"medium"}',
        TicketSummary,
    )

    assert result == TicketSummary(title="Refactor router", priority="medium")


def test_tavily_tool_search_returns_simplified_results() -> None:
    class FakeTavilyClient:
        def search(self, **kwargs):
            return {
                "answer": "A short answer",
                "results": [
                    {
                        "title": "Example",
                        "url": "https://example.com",
                        "content": "Snippet",
                    }
                ],
            }

    tool = TavilyTool(api_key="test-key", tavily_client=FakeTavilyClient())
    result = tool.search("python", limit=1)

    assert result.metadata["answer"] == "A short answer"
    assert result.output == [
        {
            "title": "Example",
            "url": "https://example.com",
            "content": "Snippet",
        }
    ]


def test_tavily_tool_requires_api_key() -> None:
    tool = TavilyTool(api_key=None)

    with pytest.raises(ToolExecutionError):
        tool.search("python")


def test_tavily_tool_extract_returns_trimmed_content() -> None:
    class FakeTavilyClient:
        def extract(self, **kwargs):
            return {
                "results": [
                    {
                        "url": kwargs["urls"][0],
                        "raw_content": "A" * 400,
                    }
                ],
            }

    tool = TavilyTool(api_key="test-key", tavily_client=FakeTavilyClient())
    result = tool.extract("https://docs.example.com")

    assert result.output[0]["url"] == "https://docs.example.com"
    assert result.output[0]["content"].endswith("...")


def test_tavily_tool_crawl_returns_cleaned_items() -> None:
    class FakeTavilyClient:
        def crawl(self, **kwargs):
            return {
                "base_url": kwargs["url"],
                "results": [
                    {
                        "url": "https://docs.example.com/retries",
                        "title": "Retries",
                        "content": "Retry guidance for network failures.",
                    }
                ],
            }

    tool = TavilyTool(api_key="test-key", tavily_client=FakeTavilyClient())
    result = tool.crawl("https://docs.example.com", instructions="Focus on retries")

    assert result.metadata["base_url"] == "https://docs.example.com"
    assert result.output == [
        {
            "title": "Retries",
            "url": "https://docs.example.com/retries",
            "content": "Retry guidance for network failures.",
        }
    ]
