# JavaxFlash v3.0.0

`JavaxFlash` is a lightweight Python AI client and router for multi-provider prompt workflows. It keeps the public API small while providing stronger foundations for production use: configurable retries, cleaner routing, structured output parsing, and optional Tavily-backed web grounding.

## Overview

`JavaxFlash` is designed for developers who want:

- one simple client for multiple AI providers
- lightweight provider routing with sensible defaults
- configurable retry and fallback behavior
- optional grounded answers using Tavily skills
- structured JSON-style output without a heavy framework

The library is intentionally synchronous and compact in `v3.0.0`. It does not include streaming, chat memory, or async support in this release.

## Installation

Install the package locally:

```bash
pip install javaxflash
```

## Quick Start

```python
from javaxFlash import Client

client = Client()
response = client.flash("Explain the difference between REST and GraphQL in simple terms.")

print(response.text)
print(response.provider)
print(response.model_used)
print(response.route_reason)
```

`ask()` is available as a convenience alias:

```python
response = client.ask("What is Python?")
```

## Core Features

- Canonical provider architecture with `flash` and `deepseek`
- Safer `POST`-based transport with timeout handling
- Configurable retry logic with backoff and jitter
- Optional provider fallback
- Structured output parsing with lightweight schemas
- Tavily-powered skills for `search`, `extract`, and `crawl`
- Automatic or manual skill usage for grounded answers
- Clean response objects with routing, retry, latency, and skill metadata

## Usage

### Basic Usage

```python
from javaxFlash import Client

client = Client()
response = client.flash("Summarize the purpose of retry logic in API clients.")

print(response.text)
```

### Provider Selection

Let the router decide:

```python
response = client.flash("What is Python used for?")
print(response.provider)
```

Force a provider:

```python
response = client.flash("Use the flash provider.", provider="flash")
response = client.flash("Analyze this architecture tradeoff.", provider="deepseek")
```

Use routing modes:

```python
fast = client.flash("Summarize HTTP status codes.", mode="fast")
reasoning = client.flash("Compare monolith vs microservices for a growing SaaS.", mode="reasoning")
```

Backward compatibility note: `provider="gemini"` is still accepted and resolves to `flash`.

### Retry Configuration

```python
from javaxFlash import Client, Config, RetryExhaustedError, TimeoutError

config = Config(
    timeout=20.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_multiplier=2.0,
    backoff_max=8.0,
    jitter=0.2,
    fallback_enabled=True,
)

client = Client(config)

try:
    response = client.flash("Summarize retry strategies for HTTP clients.")
    print(response.text)
    print(response.retry_count)
except (TimeoutError, RetryExhaustedError) as exc:
    print(exc)
```

### Tool Usage

The tool system is designed to support the AI response, not replace it. Tool data is cleaned internally and injected into the model prompt as grounding context. Users receive a normal AI answer, not raw tool output objects.

#### Automatic Skill Usage

```python
from javaxFlash import Client, Config

client = Client(
    Config(
        tavily_api_key="your-tavily-api-key",
        auto_search=True,
    )
)

response = client.flash("What is the latest Python release?")

print(response.text)
print(response.search_used)
print(response.search_query)
```

#### Manual Skill Usage

Force specific skills when you want grounded answers:

```python
response = client.flash(
    "What changed in the latest Python release?",
    skills="search",
)
```

```python
response = client.flash(
    "Summarize this page: https://docs.python.org/3/whatsnew/",
    skills=["extract"],
)
```

```python
response = client.flash(
    "Crawl docs from https://docs.example.com/retries and summarize the guidance.",
    skills=["crawl"],
    crawl_instructions="Focus on retry recommendations and edge cases.",
)
```

Supported skills in `v3.0.0`:

- `search`
- `extract`
- `crawl`

Important behavior:

- Skill output is cleaned before it is used
- Raw `ToolResult(...)` objects are not returned from `flash(...)`
- Manual and automatic skill usage both produce a final AI answer

### Structured Output

Use a lightweight schema when you want predictable JSON-shaped output.

```python
from javaxFlash import Client, JsonSchema

task_schema = JsonSchema(
    name="task_summary",
    fields={
        "title": str,
        "priority": str,
        "action_items": [str],
    },
)

client = Client()
response = client.flash(
    "Turn this into a compact task plan for backend cleanup.",
    schema=task_schema,
)

print(response.structured_output)
```

You can also use a dataclass:

```python
from dataclasses import dataclass
from javaxFlash import Client

@dataclass
class TicketSummary:
    title: str
    priority: str

client = Client()
response = client.flash("Summarize this bug report.", schema=TicketSummary)

print(response.structured_output.title)
```

## Configuration Guide

Common configuration fields:

- `timeout`
- `max_retries`
- `backoff_base`
- `backoff_multiplier`
- `backoff_max`
- `jitter`
- `retry_status_codes`
- `default_provider`
- `default_model`
- `provider_models`
- `fallback_enabled`
- `fallback_provider`
- `auto_route`
- `debug`
- `capture_raw_response`
- `auto_search`
- `tavily_api_key`
- `search_tool_name`
- `search_max_results`
- `search_timeout`

Example:

```python
from javaxFlash import Client, Config

config = Config(
    timeout=15.0,
    max_retries=2,
    default_provider="flash",
    fallback_enabled=True,
    fallback_provider="deepseek",
    auto_search=False,
    tavily_api_key="your-tavily-api-key",
)

client = Client(config)
```

### Environment Variables

Environment-based configuration is optional:

```python
from javaxFlash import Config

config = Config.from_env()
```

Supported environment variables include:

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
- `JAVAXFLASH_DEBUG`

## Response Model

Each request returns `FlashResponse`:

```python
response.text
response.provider
response.model_used
response.route_reason
response.retry_count
response.latency_ms
response.raw
response.structured_output
response.search_used
response.search_query
response.search_summary
response.skills_used
response.skills_summary
```

`raw` is only included when `capture_raw_response=True` or `include_raw=True`.

## Error Handling

Library-specific exceptions:

- `ProviderError`
- `TimeoutError`
- `RetryExhaustedError`
- `SchemaValidationError`
- `ToolExecutionError`

Typical example:

```python
from javaxFlash import Client, ToolExecutionError

client = Client()

try:
    response = client.flash("What is the latest Python release?", skills="search")
    print(response.text)
except ToolExecutionError as exc:
    print(exc)
```

## Best Practices

- Use `auto_search=True` only when you want lightweight web grounding for freshness-sensitive prompts.
- Use manual `skills=` when you know the answer should be grounded by search, extraction, or crawling.
- Keep schemas small and explicit for the best structured-output reliability.
- Enable `capture_raw_response` only for debugging or diagnostics.
- Prefer provider forcing only when you have a clear reason; otherwise let routing do the work.

## Limitations

- Synchronous only in `v3.0.0`
- No streaming support
- No async API
- No chat history or memory layer
- Tooling is currently Tavily-focused and limited to `search`, `extract`, and `crawl`
- Output quality still depends on upstream model and search provider behavior

## Examples

Working examples are provided in:

- `examples/basic_usage.py`
- `examples/provider_selection.py`
- `examples/retry_config.py`
- `examples/structured_output.py`
- `examples/tavily_search.py`

## Testing

Run the test suite:

```bash
./.venv/bin/pytest -q
```

## Version

This release is aligned with `v3.0.0`.
