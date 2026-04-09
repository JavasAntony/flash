from __future__ import annotations

from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
import json
from types import UnionType
from typing import Any, Literal, Mapping, Union, get_args, get_origin, get_type_hints

from .errors import SchemaError


@dataclass(slots=True)
class Schema:
    name: str
    fields: Mapping[str, Any]
    strict: bool = True


SchemaLike = Schema | Mapping[str, Any] | type


def schema_note(shape: SchemaLike) -> str:
    body = json.dumps(describe(shape), indent=2, ensure_ascii=True)
    return "Return the answer as valid JSON matching this schema.\n" + body


def parse_json(text: str, shape: SchemaLike) -> Any:
    try:
        data = _json(text)
    except json.JSONDecodeError as err:
        raise SchemaError("structured output was requested but the provider did not return valid JSON") from err
    return _check(data, shape, path="$")


def describe(shape: SchemaLike) -> Any:
    if isinstance(shape, Schema):
        return {key: describe(value) for key, value in shape.fields.items()}
    if isinstance(shape, Mapping):
        return {key: describe(value) for key, value in shape.items()}
    if _is_dc(shape):
        hints = get_type_hints(shape)
        return {item.name: describe(hints[item.name]) for item in fields(shape)}

    origin = get_origin(shape)
    args = get_args(shape)
    if origin in (list, tuple):
        return [describe(args[0] if args else Any)]
    if origin is dict:
        return {"type": "object", "values": describe(args[1] if len(args) > 1 else Any)}
    if origin in (Union, UnionType):
        return {"any_of": [describe(item) for item in args]}
    if origin is Literal:
        return {"enum": list(args)}
    if isinstance(shape, type) and issubclass(shape, Enum):
        return {"enum": [item.value for item in shape]}
    if shape in (str, int, float, bool):
        return shape.__name__
    if shape is Any:
        return "any"
    if shape is type(None):
        return "null"
    return getattr(shape, "__name__", str(shape))


def _json(text: str) -> Any:
    raw = text.strip()
    picks = [raw]

    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            picks.append("\n".join(lines[1:-1]).strip())

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        picks.append(raw[start : end + 1])

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end > start:
        picks.append(raw[start : end + 1])

    last: json.JSONDecodeError | None = None
    for pick in picks:
        try:
            return json.loads(pick)
        except json.JSONDecodeError as err:
            last = err
    if last is None:
        raise json.JSONDecodeError("no JSON payload found", raw, 0)
    raise last


def _check(value: Any, shape: SchemaLike | Any, *, path: str) -> Any:
    if isinstance(shape, Schema):
        return _map(value, shape.fields, path=path, strict=shape.strict)
    if isinstance(shape, Mapping):
        return _map(value, shape, path=path, strict=True)
    if _is_dc(shape):
        return shape(**_dc(value, shape, path=path))

    origin = get_origin(shape)
    args = get_args(shape)

    if shape is Any or shape is object:
        return value
    if shape is str:
        if not isinstance(value, str):
            raise SchemaError(f"{path} expected str, got {type(value).__name__}")
        return value
    if shape is bool:
        if not isinstance(value, bool):
            raise SchemaError(f"{path} expected bool, got {type(value).__name__}")
        return value
    if shape is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaError(f"{path} expected int, got {type(value).__name__}")
        return value
    if shape is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaError(f"{path} expected float, got {type(value).__name__}")
        return float(value)
    if shape is type(None):
        if value is not None:
            raise SchemaError(f"{path} expected null, got {type(value).__name__}")
        return None
    if origin in (list, tuple):
        if not isinstance(value, list):
            raise SchemaError(f"{path} expected list, got {type(value).__name__}")
        item_shape = args[0] if args else Any
        return [_check(item, item_shape, path=f"{path}[{i}]") for i, item in enumerate(value)]
    if origin is dict:
        if not isinstance(value, dict):
            raise SchemaError(f"{path} expected dict, got {type(value).__name__}")
        item_shape = args[1] if len(args) > 1 else Any
        return {str(key): _check(item, item_shape, path=f"{path}.{key}") for key, item in value.items()}
    if origin in (Union, UnionType):
        errs: list[str] = []
        for item_shape in args:
            try:
                return _check(value, item_shape, path=path)
            except SchemaError as err:
                errs.append(str(err))
        raise SchemaError("; ".join(errs))
    if origin is Literal:
        allowed = set(args)
        if value not in allowed:
            raise SchemaError(f"{path} expected one of {sorted(allowed)!r}, got {value!r}")
        return value
    if isinstance(shape, type) and issubclass(shape, Enum):
        for item in shape:
            if value == item.value:
                return item
        raise SchemaError(f"{path} expected enum value from {[item.value for item in shape]!r}, got {value!r}")
    return value


def _map(value: Any, shape: Mapping[str, Any], *, path: str, strict: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{path} expected object, got {type(value).__name__}")
    missing = [key for key, item in shape.items() if key not in value and not _is_opt(item)]
    if missing:
        raise SchemaError(f"{path} missing required keys: {', '.join(missing)}")
    if strict:
        extra = [key for key in value if key not in shape]
        if extra:
            raise SchemaError(f"{path} contains unexpected keys: {', '.join(extra)}")
    out: dict[str, Any] = {}
    for key, item_shape in shape.items():
        if key not in value:
            out[key] = None
        else:
            out[key] = _check(value[key], item_shape, path=f"{path}.{key}")
    return out


def _dc(value: Any, shape: type, *, path: str) -> dict[str, Any]:
    hints = get_type_hints(shape)
    schema = {item.name: hints[item.name] for item in fields(shape)}
    out = _map(value, schema, path=path, strict=True)
    for item in fields(shape):
        if item.name not in value and item.default is not MISSING:
            out[item.name] = item.default
        elif item.name not in value and item.default_factory is not MISSING:
            out[item.name] = item.default_factory()
    return out


def _is_dc(value: Any) -> bool:
    return isinstance(value, type) and is_dataclass(value)


def _is_opt(shape: Any) -> bool:
    origin = get_origin(shape)
    if origin not in (Union, UnionType):
        return False
    return type(None) in get_args(shape)
