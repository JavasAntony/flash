from __future__ import annotations

import sys
import time
from typing import Any

from .models import Res


def type_out(
    text: str,
    *,
    delay: float = 0.02,
    end: str = "\n",
    stream: Any = None,
) -> str:
    target = sys.stdout if stream is None else stream
    for char in text:
        target.write(char)
        target.flush()
        if delay > 0:
            time.sleep(delay)
    if end:
        target.write(end)
        target.flush()
    return text


def show_response(
    res: Res | str,
    *,
    delay: float = 0.02,
    end: str = "\n",
    stream: Any = None,
) -> str:
    text = res.text if isinstance(res, Res) else str(res)
    return type_out(text, delay=delay, end=end, stream=stream)
