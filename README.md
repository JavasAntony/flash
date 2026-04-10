# Lunox v5.0.0

`Lunox` is a compact Python library for sending prompts to multiple AI providers through one consistent API.

It focuses on:

- simple `client.ask(...)` usage
- lightweight routing between `gemini` and `deepseek`
- retry and fallback handling
- structured output parsing with `Schema`
- optional Tavily-backed `search` and `extract`
- local tool injection
- async support
- lightweight conversation history

## Installation

```bash
pip install lunox
```

Optional for Tavily-based `search` and `extract`:

```bash
pip install "lunox[tavily]"
```

This keeps `tavily-python` optional, which helps on devices where building Rust-backed dependencies is problematic.

## Quick Start

```python
from lunox import Client, Config

cfg = Config(
    provider="gemini",
    timeout=20.0,
    custom_instruction="You are Lunox. Explain things clearly for beginner developers.",
)
client = Client(cfg=cfg)
res = client.ask("Explain the difference between REST and GraphQL in simple terms.")

print(res.text)
print(res.provider)
print(res.model)
print(res.reason)
```

## Main API

```python
from lunox import Client

client = Client()
res = client.ask("Summarize retry logic in API clients.")
print(res.text)
```

Useful `Config` helpers:

- `set_instruction(text)`: set default instruction once for every request
- `set_provider(provider, model=None)`: switch default provider and optionally its model
- `set_retry_policy(...)`: tune retries and backoff in one place
- `enable_search(...)`: enable automatic Tavily-backed grounding
- `use_tavily(api_key, tool_name="tavily", limit=None)`: store Tavily settings in config
- `as_dict()`: inspect the active config as a normal dictionary

Built-in fake streaming helpers:

- `type_out(text, delay=0.02)`: print text with a typing animation
- `show_response(res, delay=0.02)`: print `Res.text` with the same effect
- `client.show(res, delay=0.02)`: instance helper if you prefer calling it from `Client`

Async works the same way:

```python
import asyncio
from lunox import AsyncClient


async def main() -> None:
    client = AsyncClient()
    res = await client.ask("Explain exponential backoff simply.")
    print(res.text)


asyncio.run(main())
```

## Lightweight History

Use a session when you want short conversation memory:

```python
from lunox import Client

client = Client()
session = client.session(max_turns=6)

session.ask("My product is a Python SDK for AI providers.")
res = session.ask("Give me three tagline ideas.")
print(res.text)
```

Or pass a shared history list directly:

```python
history: list[tuple[str, str]] = []

client.ask("Remember that my app is called Lunox Studio.", history=history, history_limit=6)
res = client.ask("What is my app called?", history=history, history_limit=6)
print(res.text)
```

## Structured Output

Use `Schema` when you want parsed output in `res.data`.

```python
from lunox import Client, Schema

client = Client()
schema = Schema(
    name="ticket",
    fields={
        "title": str,
        "priority": str,
        "items": [str],
    },
)

res = client.ask("Summarize this bug report.", schema=schema)
print(res.data)
```

## Providers

```python
res = client.ask("What is Python used for?")
fast = client.ask("Summarize HTTP status codes.", mode="fast")
reasoning = client.ask("Compare monolith vs microservices.", mode="reasoning")
forced = client.ask("Analyze this architecture tradeoff.", provider="deepseek")
```

Compatibility note:

- `provider="flash"` is still accepted and mapped to `gemini`
- the legacy `javaxFlash` package remains as a compatibility shim

## Config

```python
from lunox import Client, Config

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

Environment-based config:

```python
from lunox import Config

cfg = Config.from_env()
```

Useful environment variables:

- `LUNOX_TIMEOUT`
- `LUNOX_MAX_RETRIES`
- `LUNOX_BACKOFF_BASE`
- `LUNOX_BACKOFF_MULTIPLIER`
- `LUNOX_BACKOFF_MAX`
- `LUNOX_JITTER`
- `LUNOX_DEFAULT_PROVIDER`
- `LUNOX_DEFAULT_MODEL`
- `LUNOX_FALLBACK_PROVIDER`
- `LUNOX_PROVIDER_MODELS`
- `LUNOX_AUTO_ROUTE`
- `LUNOX_AUTO_SEARCH`
- `LUNOX_TAVILY_API_KEY`
- `LUNOX_SEARCH_TOOL_NAME`
- `LUNOX_SEARCH_MAX_RESULTS`
- `LUNOX_SEARCH_TIMEOUT`

## Local Tools And Search

```python
from lunox import Client

client = Client()
client.add_fn("project_info", lambda: {"title": "Project", "content": "The library focuses on multi-provider routing."})

res = client.ask("Summarize the current project focus.", tool_calls={"project_info": {}})
print(res.text)
```

```python
res = client.ask("What is the latest Python release?", skills="search")
print(res.search_query)
```

## Development

```bash
pytest
python3 -m compileall lunox javaxFlash tests examples
```
