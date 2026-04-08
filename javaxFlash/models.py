from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FlashResponse:
    text: str
    model_used: str
    provider: str
    raw: Any = None
    route_reason: str = ""
    error: str | None = None


AIResponse = FlashResponse
