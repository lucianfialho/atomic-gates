"""
Minimal JSON Schema validator — self-contained, subset only.

Supported keywords:
  type, required, properties, additionalProperties, items, minItems,
  minLength, minProperties, enum, const, uniqueItems.

Intentionally does not support $ref, allOf/anyOf/oneOf, patternProperties,
format, or any other advanced feature. Schemas used by gates must stay
within this subset.
"""

from __future__ import annotations

from typing import Any, List


class ValidationError(Exception):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path or '<root>'}: {message}")
        self.path = path
        self.message = message


_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def validate(instance: Any, schema: dict, path: str = "") -> None:
    """Raise ValidationError if `instance` does not match `schema`."""
    if "const" in schema and instance != schema["const"]:
        raise ValidationError(path, f"expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(path, f"expected one of {schema['enum']}, got {instance!r}")

    if "type" in schema:
        expected = schema["type"]
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(_matches_type(instance, t) for t in expected_types):
            raise ValidationError(
                path, f"expected type {expected}, got {type(instance).__name__}"
            )

    if isinstance(instance, dict):
        _validate_object(instance, schema, path)
    elif isinstance(instance, list):
        _validate_array(instance, schema, path)
    elif isinstance(instance, str):
        _validate_string(instance, schema, path)


def _matches_type(instance: Any, type_name: str) -> bool:
    if type_name not in _TYPE_MAP:
        return False
    expected = _TYPE_MAP[type_name]
    if type_name == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if type_name == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    return isinstance(instance, expected)


def _validate_object(instance: dict, schema: dict, path: str) -> None:
    required = schema.get("required", [])
    for key in required:
        if key not in instance:
            raise ValidationError(path, f"missing required property '{key}'")

    if "minProperties" in schema and len(instance) < schema["minProperties"]:
        raise ValidationError(path, f"object must have at least {schema['minProperties']} properties")

    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for key, value in instance.items():
        child_path = f"{path}.{key}" if path else key
        if key in properties:
            validate(value, properties[key], child_path)
        elif additional is False:
            raise ValidationError(path, f"unexpected property '{key}'")
        elif isinstance(additional, dict):
            validate(value, additional, child_path)


def _validate_array(instance: list, schema: dict, path: str) -> None:
    if "minItems" in schema and len(instance) < schema["minItems"]:
        raise ValidationError(path, f"array must have at least {schema['minItems']} items")

    if schema.get("uniqueItems") and len(instance) != len({_hashable(i) for i in instance}):
        raise ValidationError(path, "array items must be unique")

    item_schema = schema.get("items")
    if item_schema:
        for i, item in enumerate(instance):
            validate(item, item_schema, f"{path}[{i}]")


def _validate_string(instance: str, schema: dict, path: str) -> None:
    if "minLength" in schema and len(instance) < schema["minLength"]:
        raise ValidationError(path, f"string must be at least {schema['minLength']} chars")


def _hashable(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return repr(value)
    return value


def validate_or_errors(instance: Any, schema: dict) -> List[str]:
    """Return a list of error messages (empty if valid)."""
    try:
        validate(instance, schema)
        return []
    except ValidationError as e:
        return [str(e)]
