from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Any

from .config import Config, norm_provider
from .errors import MissingProviderError, ProviderError
from .models import Caps, Req, Res
from .transport import Transport


class Provider(ABC):
    name: str
    url: str
    caps = Caps()

    def __init__(self, cfg: Config, net: Transport) -> None:
        self.cfg = cfg
        self.net = net

    def run(self, req: Req) -> Res:
        payload = self.build(req)
        net_res = self.net.post(url=self.url, data=payload, provider=self.name)
        raw = net_res.data
        think, text = self.read_text(raw)
        if not text:
            raise ProviderError(f"{self.name} response did not contain usable text", provider=self.name)
        return Res(
            text=text.strip(),
            provider=self.name,
            model=self.read_model(raw, req),
            retries=net_res.retries,
            latency=net_res.latency,
            raw=raw if req.raw else None,
            think=think,
            caps=self.caps,
        )

    @abstractmethod
    def build(self, req: Req) -> dict[str, Any]:
        raise NotImplementedError

    def read_text(self, raw: Any) -> tuple[str | None, str]:
        if isinstance(raw, str):
            return self._split_text(raw)
        if isinstance(raw, dict):
            for key in ("text", "response", "answer", "result", "message", "content"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    return self._split_text(val)
            data = raw.get("data")
            if isinstance(data, dict):
                return self.read_text(data)
            items = raw.get("candidates")
            if isinstance(items, list):
                thinks: list[str] = []
                texts: list[str] = []
                for item in items:
                    if isinstance(item, dict):
                        think, text = self.read_text(item)
                        if think:
                            thinks.append(think)
                        if text:
                            texts.append(text)
                if texts:
                    return ("\n".join(thinks) if thinks else None, "\n".join(texts))
            items = raw.get("parts")
            if isinstance(items, list):
                thinks: list[str] = []
                parts = []
                for item in items:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            think, final = self._split_text(text.strip())
                            if think:
                                thinks.append(think)
                            if final:
                                parts.append(final)
                if parts:
                    return ("\n".join(thinks) if thinks else None, "\n".join(parts))
        if isinstance(raw, list):
            thinks: list[str] = []
            texts: list[str] = []
            for item in raw:
                think, text = self.read_text(item)
                if think:
                    thinks.append(think)
                if text:
                    texts.append(text)
            if texts:
                return ("\n".join(thinks) if thinks else None, "\n".join(texts))
        return (None, "")

    def read_model(self, raw: Any, req: Req) -> str:
        if isinstance(raw, dict):
            for key in ("model", "model_used"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    return val
        return self.cfg.pick_model(self.name, req.model)

    def _split_text(self, text: str) -> tuple[str | None, str]:
        raw = text.strip()
        if not raw:
            return (None, "")
        match = re.search(r"<thinking>(.*?)</thinking>", raw, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return (None, raw)
        think = match.group(1).strip() or None
        final = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
        return (think, final)


class Gemini(Provider):
    name = "gemini"
    url = "https://api.siputzx.my.id/api/ai/gemini-lite"
    caps = Caps(cost="low")

    def build(self, req: Req) -> dict[str, Any]:
        data: dict[str, Any] = {
            "prompt": req.prompt,
            "model": self.cfg.pick_model(self.name, req.model),
        }
        if req.system:
            data["system"] = req.system
        temp = req.opts.get("temperature")
        if temp is not None:
            data["temperature"] = temp
        return data


class DeepSeek(Provider):
    name = "deepseek"
    url = "https://api.siputzx.my.id/api/ai/deepseekr1"

    def build(self, req: Req) -> dict[str, Any]:
        data = {
            "prompt": req.prompt,
            "model": self.cfg.pick_model(self.name, req.model),
            "temperature": req.opts.get("temperature", self.cfg.deepseek_temp),
        }
        if req.system:
            data["system"] = req.system
        return data


class ProviderMap:
    def __init__(self, items: list[Provider] | tuple[Provider, ...]) -> None:
        self.items: dict[str, Provider] = {}
        for item in items:
            self.add(item)

    def add(self, item: Provider) -> None:
        self.items[item.name] = item

    def get(self, name: str) -> Provider:
        key = norm_provider(name)
        try:
            return self.items[key]
        except KeyError as err:
            raise MissingProviderError(
                f"Unknown provider '{name}'. Available providers: {', '.join(sorted(self.items))}",
                provider=key,
            ) from err

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.items))

    def caps_for(self, name: str) -> Caps:
        return self.get(name).caps
