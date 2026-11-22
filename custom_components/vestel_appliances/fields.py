"""Discovery-based register codecs; no network access or appliance control.

Unknown/malformed fields fail closed. Bit updates always require a current
register value so an unrelated setting is never silently cleared.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaError(ValueError):
    pass


def integer(value: Any) -> int:
    if isinstance(value, bool):
        raise SchemaError("Boolean is not a register value")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        result = int(value)
    else:
        raise SchemaError("Missing or invalid register value")
    if not 0 <= result <= 65535:
        raise SchemaError("Register is outside the 16-bit range")
    return result


@dataclass(frozen=True)
class Field:
    definition: dict

    @property
    def command(self) -> str:
        command = self.definition.get("commandName", "")
        if not isinstance(command, str) or len(command) != 7 or not command.isalnum():
            raise SchemaError("Invalid register name")
        return command

    def layout(self) -> tuple[int, int] | None:
        position, length = self.definition.get("position"), self.definition.get("length")
        if position is None and length is None:
            return None
        if type(position) is not int or type(length) is not int:
            raise SchemaError("Incomplete bit layout")
        if position < 0 or length <= 0 or position + length > 16:
            raise SchemaError("Invalid bit layout")
        return position, length

    def raw(self, registers: dict) -> int:
        value = integer(registers.get(self.command))
        layout = self.layout()
        if layout is None:
            return value
        position, length = layout
        return (value >> position) & ((1 << length) - 1)

    def decode(self, registers: dict) -> Any:
        value = self.raw(registers)
        kind = self.definition.get("valueType")
        if kind == "Enum":
            for item in self.definition.get("values", []):
                if item.get("commandValue") == value:
                    return item.get("value")
            return None
        if kind == "Boolean":
            expected = self.definition.get("commandValue")
            if type(expected) is not int:
                raise SchemaError("Boolean comparison has no definition")
            return value == expected
        # The offset is model-defined for AC temperature only. Integer and
        # timer registers must not inherit it merely by sharing commandValue.
        if self.definition.get("key") == "Climate.AirConditioner.Setting.Temperature":
            offset = self.definition.get("commandValue")
            if type(offset) is not int:
                raise SchemaError("Temperature offset is missing")
            return value + offset
        return value

    def replace_bits(self, registers: dict, encoded_value: int) -> str:
        """Build bytes for review/testing only; this never transmits anything."""
        value = integer(encoded_value)
        layout = self.layout()
        if layout is None:
            result = value
        else:
            position, length = layout
            mask = (1 << length) - 1
            if value > mask:
                raise SchemaError("Value does not fit: possibly a pre-shifted sentinel")
            current = integer(registers.get(self.command))
            result = (current & ~(mask << position)) | (value << position)
        return f"{self.command}{result:05d}"


def decode_snapshot(snapshot: dict) -> list[dict]:
    results = []
    for device in snapshot["devices"]:
        fields = []
        for group in ("settings", "options", "status", "errors"):
            for definition in (device.get("discovery") or {}).get(group, []):
                try:
                    field = Field(definition)
                    raw = field.raw(device.get("registers") or {})
                    value = field.decode(device.get("registers") or {})
                    fields.append({"group": group, "key": definition["key"],
                                   "register": field.command, "raw_field": raw,
                                   "value": value, "validation": "schema_decode_only"})
                except (SchemaError, KeyError):
                    fields.append({"group": group, "key": definition.get("key"),
                                   "value": None, "validation": "unavailable_or_invalid"})
        results.append({"alias": device["alias"], "metadata": device["metadata"], "fields": fields})
    return results
