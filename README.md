# JavaxFlash v4.0.0

`JavaxFlash` is a small Python library for sending prompts to multiple AI providers through one consistent client API.

It focuses on a few practical things:

- simple `client.flash(...)` usage
- lightweight provider routing between `flash` and `deepseek`
- retry and fallback handling
- structured output parsing
- optional Tavily-backed `search` and `extract`
- local tool injection
- async support
- lightweight session memory

This library is intentionally small. It does not include streaming, and it does not include agent mode in `v4.0.0`.

## Who This Is For

`JavaxFlash` fits best if you want:

- one compact client for multiple providers
- a cleaner wrapper around prompt calls
- optional grounded answers with web search or extraction
- structured JSON-like output without a large framework
- a library that stays readable and easy to extend

## Installation

Install the package:

```bash
pip install javaxflash
```

Optional for Tavily-based `search` and `extract`:

```bash
pip install tavily-python
```

## Quick Start

```python
from javaxFlash import Client

client = Client()
res = client.flash("Explain the difference between REST and GraphQL in simple terms.")

print(res.text)
print(res.provider)
print(res.model)
print(res.reason)
```

`ask()` is just an alias for `flash()`:

```python
res = client.ask("What is Python?")
```

## The Main Idea

Most users only need this mental model:

1. Create `Client()`
2. Call `client.flash(...)`
3. Optionally add `provider=`, `schema=`, `skills=`, or `tool_calls=`
4. Read `res.text` or `res.data`

If you start there, the rest of the library feels much simpler.

## Core API

### `Client`

Main sync client.

```python
from javaxFlash import Client

client = Client()
res = client.flash("Summarize retry logic in API clients.")
print(res.text)
```

### `AsyncClient`

Async wrapper for the same API.

```python
import asyncio
from javaxFlash import AsyncClient


async def main() -> None:
    client = AsyncClient()
    res = await client.flash("Explain exponential backoff simply.")
    print(res.text)


asyncio.run(main())
```

### `Session`

Simple short-term conversation history.

```python
from javaxFlash import Client

client = Client()
session = client.session(max_turns=6)

session.ask("My product is a Python SDK for AI providers.")
res = session.ask("Give me three tagline ideas.")
print(res.text)
```

## Providers

Built-in providers:

- `flash`
- `deepseek`

Let the router choose:

```python
res = client.flash("What is Python used for?")
print(res.provider)
```

Force a provider:

```python
res = client.flash("Use the flash provider.", provider="flash")
res = client.flash("Analyze this architecture tradeoff.", provider="deepseek")
```

Routing modes:

```python
fast = client.flash("Summarize HTTP status codes.", mode="fast")
reasoning = client.flash("Compare monolith vs microservices.", mode="reasoning")
```

Compatibility note:

- `provider="gemini"` is accepted and mapped to `flash`

## Configuration

Use `Config` when you want to control timeout, retries, fallback, search settings, or hooks.

```python
from javaxFlash import Client, Config

cfg = Config(
    timeout=20.0,
    retries=3,
    backoff=0.5,
    backoff_rate=2.0,
    backoff_max=8.0,
    jitter=0.2,
    fallback=True,
)

client = Client(cfg=cfg)
```

Common fields:

- `timeout`
- `retries`
- `backoff`
- `backoff_rate`
- `backoff_max`
- `jitter`
- `retry_codes`
- `provider`
- `model`
- `models`
- `fallback`
- `fallback_provider`
- `auto_route`
- `raw`
- `auto_search`
- `auto_tools`
- `tavily_key`
- `search_tool`
- `search_limit`
- `search_timeout`
- `hooks`

Environment-based config is also supported:

```python
from javaxFlash import Config

cfg = Config.from_env()
```

Useful environment variables:

- `JAVAXFLASH_TIMEOUT`
- `JAVAXFLASH_MAX_RETRIES`
- `JAVAXFLASH_BACKOFF_BASE`
- `JAVAXFLASH_BACKOFF_MULTIPLIER`
- `JAVAXFLASH_BACKOFF_MAX`
- `JAVAXFLASH_JITTER`
- `JAVAXFLASH_DEFAULT_PROVIDER`
- `JAVAXFLASH_DEFAULT_MODEL`
- `JAVAXFLASH_FALLBACK_PROVIDER`
- `JAVAXFLASH_PROVIDER_MODELS`
- `JAVAXFLASH_AUTO_ROUTE`
- `JAVAXFLASH_AUTO_SEARCH`
- `JAVAXFLASH_TAVILY_API_KEY`
- `JAVAXFLASH_SEARCH_TOOL_NAME`
- `JAVAXFLASH_SEARCH_MAX_RESULTS`
- `JAVAXFLASH_SEARCH_TIMEOUT`

## Retries And Fallback

```python
from javaxFlash import Client, Config, RetryError, TimeoutError

client = Client(
    cfg=Config(
        timeout=20.0,
        retries=3,
        fallback=True,
    )
)

try:
    res = client.flash("Summarize retry strategies for HTTP clients.")
    print(res.text)
    print(res.retries)
except (TimeoutError, RetryError) as err:
    print(err)
```

Fallback is provider-level. If the chosen provider fails and fallback is enabled, the client can retry the request on another provider.

## Structured Output

Use `Schema` or a dataclass when you want parsed output in `res.data`.

### With `Schema`

```python
from javaxFlash import Client, Schema

task_schema = Schema(
    name="task_summary",
    fields={
        "title": str,
        "priority": str,
        "items": [str],
    },
)

client = Client()
res = client.flash(
    "Turn this into a compact task plan.",
    schema=task_schema,
)

print(res.data)
```

### With a dataclass

```python
from dataclasses import dataclass
from javaxFlash import Client


@dataclass
class Ticket:
    title: str
    priority: str


client = Client()
res = client.flash("Summarize this bug report.", schema=Ticket)
print(res.data.title)
```

Supported schema shapes include:

- basic Python types
- lists such as `[str]`
- `Enum`
- `Literal`
- optional values such as `str | None`
- dataclass defaults

Important note:

- structured output depends on the upstream model actually returning valid JSON
- if the provider returns invalid JSON, `SchemaError` is raised

## Tools And Skills

There are two different concepts:

### 1. Local tools

These are Python functions you register yourself.

```python
from javaxFlash import Client

client = Client()

client.register_function(
    "project_context",
    lambda: {
        "title": "Library focus",
        "content": "This SDK focuses on multi-provider routing, retries, and structured output.",
    },
)

res = client.flash(
    "Write a short project summary.",
    tool_calls={"project_context": {}},
)

print(res.text)
print(res.tools)
```

### 2. Skills

Skills are built-in prompt-grounding helpers currently backed by Tavily:

- `search`
- `extract`

Manual skill usage:

```python
from javaxFlash import Client, Config

client = Client(cfg=Config(tavily_key="your-tavily-api-key"))

res = client.flash(
    "What changed in the latest Python release?",
    skills="search",
)

print(res.text)
print(res.searched)
print(res.search_query)
```

```python
res = client.flash(
    "Summarize this page: https://docs.python.org/3/whatsnew/",
    skills=["extract"],
)
```

Direct tool-style helpers are also available:

```python
client.use_tavily()

print(client.search("latest Python release", limit=3))
print(client.extract("https://docs.python.org/3/whatsnew/"))
```

Important behavior:

- `flash()` does not automatically run search by default
- manual `skills="search"` and `skills=["extract"]` are supported
- `use_search=True` is also supported for explicit search usage
- tool output is injected as context, and the returned result is still a normal AI response
- raw `ToolRes(...)` objects are not returned from `flash(...)`

`auto_search` and `auto_tools` exist for opt-in behavior, but for most users explicit skill usage is clearer and safer.

## Observability Hooks

You can listen to client events through `hooks`.

```python
from javaxFlash import Client, Config


def log_event(event: str, payload: dict) -> None:
    print(event, payload)


client = Client(cfg=Config(hooks=(log_event,)))
res = client.flash("Summarize HTTP retries.")
```

Common emitted events include:

- `flash_requested`
- `tool_called`
- `fallback_triggered`
- `response_received`

## Response Object

Each request returns `Res`.

Common fields:

```python
res.text
res.provider
res.model
res.reason
res.retries
res.latency
res.data
res.skills
res.tools
res.searched
res.search_query
res.search_note
res.skill_note
res.think
res.caps
```

`res.raw` is included only when `raw=True`.

`res.think` is populated when a provider response contains a hidden `<thinking>...</thinking>` section and a clean final answer outside it.

## Errors

Main exceptions:

- `ProviderError`
- `MissingProviderError`
- `TimeoutError`
- `RetryError`
- `SchemaError`
- `ToolError`

Example:

```python
from javaxFlash import Client, ToolError

client = Client()

try:
    res = client.flash("What is the latest Python release?", skills="search")
    print(res.text)
except ToolError as err:
    print(err)
```

## Examples

Available examples:

- `examples/basic_usage.py`
- `examples/provider_selection.py`
- `examples/retry_config.py`
- `examples/structured_output.py`
- `examples/tavily_search.py`
- `examples/tool_registration.py`

Note for new users:

- examples are meant to be run from the repository root
- examples that use real providers depend on network access
- Tavily examples also require `tavily-python` and a valid Tavily API key
- some structured-output examples may fail if the upstream provider does not return valid JSON for that prompt

## Testing

Run tests:

```bash
./.venv/bin/pytest -q
```

Quick syntax check:

```bash
python3 -m compileall javaxFlash tests examples
```

## Limitations

- no streaming support
- no built-in agent mode
- output quality still depends on upstream providers
- structured output reliability depends on model compliance
- Tavily-backed features require extra dependency and API access

## Version

Current version: `4.0.0`
