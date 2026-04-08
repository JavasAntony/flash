from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import json
from types import UnionType
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from .errors import SchemaValidationError


@dataclass(slots=True)
class Schema:
    name: str
    fields: Mapping[str, Any]
    strict: bool = True


SchemaLike = Schema | Mapping[str, Any] | type


def schema_instruction_block(schema: SchemaLike) -> str:
    description = json.dumps(describe_schema(schema), indent=2, ensure_ascii=True)
    return (
        "Return the answer as valid JSON matching this schema.\n"
        f"{description}"
    )


def parse_structured_output(text: str, schema: SchemaLike) -> Any:
    try:
        payload = _extract_json_payload(text)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            "structured output was requested but the provider did not return valid JSON"
        ) from exc
    return _validate_value(payload, schema, path="$")


def describe_schema(schema: SchemaLike) -> Any:
    if isinstance(schema, Schema):
        return {key: describe_schema(value) for key, value in schema.fields.items()}
    if isinstance(schema, Mapping):
        return {key: describe_schema(value) for key, value in schema.items()}
    if _is_dataclass_type(schema):
        hints = get_type_hints(schema)
        return {field.name: describe_schema(hints[field.name]) for field in fields(schema)}

    origin = get_origin(schema)
    args = get_args(schema)

    if origin in (list, tuple):
        return [describe_schema(args[0] if args else Any)]
    if origin is dict:
        return {
            "type": "object",
            "values": describe_schema(args[1] if len(args) > 1 else Any),
        }
    if origin in (Union, UnionType):
        return {"any_of": [describe_schema(item) for item in args]}
    if schema in (str, int, float, bool):
        return schema.__name__
    if schema is Any:
        return "any"
    if schema is type(None):
        return "null"
    return getattr(schema, "__name__", str(schema))


def _extract_json_payload(text: str) -> Any:
    stripped = text.strip()
    candidates = [stripped]

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            candidates.append("\n".join(lines[1:-1]).strip())

    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if object_start != -1 and object_end > object_start:
        candidates.append(stripped[object_start : object_end + 1])

    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if array_start != -1 and array_end > array_start:
        candidates.append(stripped[array_start : array_end + 1])

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    if last_error is None:
        raise json.JSONDecodeError("no JSON payload found", stripped, 0)
    raise last_error


def _validate_value(value: Any, schema: SchemaLike | Any, *, path: str) -> Any:
    if isinstance(schema, Schema):
        return _validate_mapping(value, schema.fields, path=path, strict=schema.strict)
    if isinstance(schema, Mapping):
        return _validate_mapping(value, schema, path=path, strict=True)
    if _is_dataclass_type(schema):
        validated = _validate_dataclass(value, schema, path=path)
        return schema(**validated)

    origin = get_origin(schema)
    args = get_args(schema)

    if schema is Any or schema is object:
        return value
    if schema is str:
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path} expected str, got {type(value).__name__}")
        return value
    if schema is bool:
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path} expected bool, got {type(value).__name__}")
        return value
    if schema is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaValidationError(f"{path} expected int, got {type(value).__name__}")
        return value
    if schema is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaValidationError(f"{path} expected float, got {type(value).__name__}")
        return float(value)
    if schema is type(None):
        if value is not None:
            raise SchemaValidationError(f"{path} expected null, got {type(value).__name__}")
        return None

    if origin in (list, tuple):
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path} expected list, got {type(value).__name__}")
        item_schema = args[0] if args else Any
        return [
            _validate_value(item, item_schema, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]

    if origin is dict:
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path} expected dict, got {type(value).__name__}")
        value_schema = args[1] if len(args) > 1 else Any
        return {
            str(key): _validate_value(item, value_schema, path=f"{path}.{key}")
            for key, item in value.items()
        }

    if origin in (Union, UnionType):
        errors: list[str] = []
        for item_schema in args:
            try:
                return _validate_value(value, item_schema, path=path)
            except SchemaValidationError as exc:
                errors.append(str(exc))
        raise SchemaValidationError("; ".join(errors))

    return value


def _validate_mapping(
    value: Any,
    schema: Mapping[str, Any],
    *,
    path: str,
    strict: bool,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path} expected object, got {type(value).__name__}")

    missing = [key for key in schema if key not in value]
    if missing:
        raise SchemaValidationError(f"{path} missing required keys: {', '.join(missing)}")

    if strict:
        extra = [key for key in value if key not in schema]
        if extra:
            raise SchemaValidationError(f"{path} contains unexpected keys: {', '.join(extra)}")

    return {
        key: _validate_value(value[key], item_schema, path=f"{path}.{key}")
        for key, item_schema in schema.items()
    }


def _validate_dataclass(value: Any, schema: type, *, path: str) -> dict[str, Any]:
    hints = get_type_hints(schema)
    shape = {field.name: hints[field.name] for field in fields(schema)}
    return _validate_mapping(value, shape, path=path, strict=True)


def _is_dataclass_type(value: Any) -> bool:
    return isinstance(value, type) and is_dataclass(value)
