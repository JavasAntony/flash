from __future__ import annotations

from enum import Enum
from unittest.mock import Mock

import pytest
import requests

from lunox import Config, RetryError, Schema, Tavily, ToolError
from lunox.schema import parse_json
from lunox.transport import Transport


class DummyRes:
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
        DummyRes(429, {"error": "slow down"}, text="slow down"),
        DummyRes(200, {"text": "ok", "model": "gemini"}),
    ]
    delays: list[float] = []
    net = Transport(
        Config(retries=2, backoff=0.5, jitter=0.0),
        session=session,
        sleep=delays.append,
        rand=lambda start, end: 0.0,
    )

    res = net.post(url="https://example.com", data={"prompt": "hello"}, provider="gemini")

    assert res.retries == 1
    assert delays == [0.5]


def test_transport_raises_retry_error_after_repeated_timeouts() -> None:
    session = Mock()
    session.post.side_effect = requests.Timeout("network timeout")
    net = Transport(
        Config(retries=2, jitter=0.0),
        session=session,
        sleep=lambda _: None,
        rand=lambda start, end: 0.0,
    )

    with pytest.raises(RetryError) as err:
        net.post(url="https://example.com", data={"prompt": "hello"}, provider="gemini")

    assert err.value.tries == 3


class Priority(Enum):
    LOW = "low"
    HIGH = "high"


def test_parse_json_supports_enum_and_optional_fields() -> None:
    schema = Schema(
        name="ticket",
        fields={
            "title": str,
            "priority": Priority,
            "owner": str | None,
        },
    )

    res = parse_json('{"title":"Router cleanup","priority":"high"}', schema)
    assert res == {"title": "Router cleanup", "priority": Priority.HIGH, "owner": None}


def test_parse_json_supports_mapping_schemas() -> None:
    res = parse_json('{"title":"Refactor router","priority":"medium"}', {"title": str, "priority": str})
    assert res == {"title": "Refactor router", "priority": "medium"}


def test_tavily_search_returns_simplified_results() -> None:
    class FakeClient:
        def search(self, **kwargs):
            return {
                "answer": "A short answer",
                "results": [{"title": "Example", "url": "https://example.com", "content": "Snippet"}],
            }

    tool = Tavily(api_key="test-key", client=FakeClient())
    res = tool.search("python", limit=1)

    assert res.meta["answer"] == "A short answer"
    assert res.items == [{"title": "Example", "url": "https://example.com", "content": "Snippet"}]


def test_tavily_requires_api_key() -> None:
    tool = Tavily(api_key=None)
    with pytest.raises(ToolError):
        tool.search("python")


def test_tavily_extract_returns_trimmed_content() -> None:
    class FakeClient:
        def extract(self, **kwargs):
            return {"results": [{"url": kwargs["urls"][0], "raw_content": "A" * 400}]}

    tool = Tavily(api_key="test-key", client=FakeClient())
    res = tool.extract("https://docs.example.com")

    assert res.items[0]["url"] == "https://docs.example.com"
    assert res.items[0]["content"].endswith("...")
