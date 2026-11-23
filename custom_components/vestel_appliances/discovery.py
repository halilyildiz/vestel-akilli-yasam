"""Validate unknown model descriptions before exposing any write controls."""
from __future__ import annotations

from typing import Any
import math
from copy import deepcopy

from .fields import Field, SchemaError
from .families import FAMILY_PROFILES

GROUPS = ("settings", "options", "commands", "status", "errors", "programs")
TYPES = {"Enum", "Boolean", "Integer", "Number", "BinaryInteger"}


def prepare_discovery(schema: Any, family: str) -> dict[str, Any]:
    """Project monitoring-only families onto validated read-only fields.

    APK demo_ov has ambiguous duplicate command keys; demo_td has conflicting
    start semantics. Neither is allowed to create or send write controls.
    Keep the original object untouched for callers caching raw responses.
    """
    if not isinstance(schema, dict) or schema.get("deviceType") != family:
        raise SchemaError("device_type_mismatch")
    profile = FAMILY_PROFILES[family]
    if profile.writable:
        return validate_discovery(schema, family)
    projected = {key: deepcopy(value) for key, value in schema.items()
                 if key not in GROUPS + ("settingRelations", "optionRelations")}
    for group in ("status", "errors"):
        projected[group] = deepcopy(schema.get(group, []))
    if family == "TD" and isinstance(projected["status"], list):
        for definition in projected["status"]:
            if (isinstance(definition, dict)
                    and definition.get("key") in {
                        "LaundryCare.TumbleDryer.Status.RemoteControl",
                        "LaundryCare.TumbleDryer.Status.PowerStatus.Failure",
                    }
                    and definition.get("valueType") == "Boolean"
                    and "commandValue" not in definition):
                # TDCloudEntityToCloudDomain explicitly compares both to 1.
                definition["commandValue"] = 1
    return validate_discovery(projected, family)


def validate_discovery(schema: Any, family: str) -> dict[str, Any]:
    """Fail one incompatible device closed; never silently drop its constraints."""
    if not isinstance(schema, dict) or schema.get("deviceType") != family:
        raise SchemaError("device_type_mismatch")
    count = 0
    for group in GROUPS:
        definitions = schema.get(group, [])
        if not isinstance(definitions, list):
            raise SchemaError("invalid_definition_group")
        keys: set[str] = set()
        for definition in definitions:
            if not isinstance(definition, dict):
                raise SchemaError("invalid_definition")
            key = definition.get("key")
            if not isinstance(key, str) or not key or key in keys:
                raise SchemaError("invalid_definition_key")
            keys.add(key)
            if definition.get("valueType") not in TYPES:
                raise SchemaError("unsupported_value_type")
            Field(definition).command
            # RF NoError entries are read-only placeholders with -1/-1,
            # deliberately omitted from entity creation by the binary platform.
            placeholder = group == "errors" and key.endswith(".NoError") and definition.get("position") == -1 and definition.get("length") == -1
            if not placeholder:
                Field(definition).layout()
            values = definition.get("values", [])
            if not isinstance(values, list) or any(
                not isinstance(v, dict) or not isinstance(v.get("value"), str)
                or type(v.get("commandValue")) is not int for v in values
            ):
                raise SchemaError("invalid_enum")
            _structure(definition)
            count += 1
    for group in ("settingRelations", "optionRelations"):
        relations = schema.get(group, [])
        if not isinstance(relations, list):
            raise SchemaError("invalid_relations")
        for relation in relations:
            if not isinstance(relation, dict) or not isinstance(relation.get("key"), str):
                raise SchemaError("invalid_relation")
            _structure(relation)
    if not count:
        raise SchemaError("empty_description")
    return schema


def _structure(value: Any, depth: int = 0) -> None:
    """Validate nested constraint containers without rewriting their semantics."""
    if depth > 16:
        raise SchemaError("nested_description")
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"includedSettings", "includedOptions", "supportedStates", "supportedPhases",
                       "relations", "andCondition", "statements", "values"}:
                if not isinstance(child, list) or any(not isinstance(v, dict) for v in child):
                    raise SchemaError("invalid_constraint_list")
            if key == "valueLimits":
                if not isinstance(child, dict):
                    raise SchemaError("invalid_limits")
                for name in ("min", "max", "step"):
                    if name in child and (type(child[name]) not in (int, float) or not math.isfinite(child[name])):
                        raise SchemaError("invalid_numeric_limit")
            _structure(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _structure(child, depth + 1)
