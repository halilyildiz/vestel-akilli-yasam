"""Model-specific controls and conservative state validation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .fields import Field, SchemaError, integer


@dataclass(frozen=True)
class Readback:
    """Expected register values and the bits actually targeted by a write."""

    values: dict[str, int]
    masks: dict[str, int]

    def matches(self, registers: dict) -> bool:
        if not self.values or not isinstance(registers, dict):
            return False
        try:
            return all(
                integer(registers.get(key)) & self.masks[key] == value & self.masks[key]
                for key, value in self.values.items()
            )
        except SchemaError:
            return False


@dataclass
class Device:
    metadata: dict
    discovery: dict
    registers: dict
    read_ok: bool = True

    @property
    def family(self):
        return self.metadata["deviceType"]

    def definitions(self, *groups):
        return [item for group in groups for item in self.discovery.get(group, [])]

    def find(self, key):
        return next((d for d in self.definitions("settings", "options", "commands", "status", "programs") if d.get("key") == key), None)

    def find_suffix(self, suffix, *groups):
        return next((d for d in self.definitions(*(groups or ("settings", "options", "commands", "status"))) if d.get("key", "").endswith(suffix)), None)

    def decode(self, definition):
        if not definition:
            return None
        try:
            return Field(definition).decode(self.registers)
        except SchemaError:
            return None

    def status(self, suffix):
        return self.decode(self.find_suffix(suffix, "status"))

    def refrigerator_door_open(self):
        # APK RFCloudEntityToCloudDomain maps RFDOORA == 3 to closed and
        # 0/1/2 to open. It does not distinguish the individual compartments.
        if self.family != "RF":
            return None
        definition = self.find_suffix(".Status.Door", "status")
        if not definition:
            return None
        try:
            value = Field(definition).raw(self.registers)
            return value != 3 if value in {0, 1, 2, 3} else None
        except SchemaError:
            return None

    def context(self, definition):
        """Program/mode-specific allowed values, retaining all constraints."""
        key = definition["key"]
        included = None
        if self.family == "AC" and ".Setting." in key:
            mode = self.find_suffix(".Setting.Mode", "settings")
            current = self.decode(mode)
            mode_choice = next((v for v in (mode or {}).get("values", []) if v.get("value") == current), None)
            if mode_choice and key != mode["key"]:
                included = next((v for v in mode_choice.get("includedSettings", []) if v.get("key") == key), {})
        elif self.family in {"DW", "WD"} and ".Option." in key:
            selected = self.status(".SelectedProgram")
            program_name = selected.replace(".Status.SelectedProgram.", ".Program.") if selected else None
            program = next((p for p in self.discovery.get("programs", []) if p.get("key") == program_name), None)
            # Delay is a device-level option and may be omitted from a program.
            if program:
                included = next((v for v in program.get("includedOptions", []) if v.get("key") == key), None)
                if included is None and not key.endswith((".Delay", ".DelayTimer")):
                    included = {}
        return included

    def condition(self, key):
        definition = self.find(key)
        if definition:
            try:
                return bool(Field(definition).raw(self.registers))
            except SchemaError:
                return False
        # Conditions also name individual enum choices.
        parent = key.rsplit(".", 1)[0]
        definition = self.find(parent)
        return self.decode(definition) == key if definition else False

    def rules(self, definition):
        for relation in self.definitions("settingRelations", "optionRelations"):
            if relation.get("key") != definition["key"]:
                continue
            for rule in relation.get("relations", []):
                conditions = rule.get("andCondition", [])
                if conditions and all(self.condition(c.get("key", "")) for c in conditions):
                    yield rule.get("statements", [])

    def values(self, definition):
        values = [v for v in definition.get("values", []) if "commandValue" in v]
        included = self.context(definition)
        if included is not None:
            if not included or included.get("isSelectable") is False:
                return []
            if "values" in included:
                names = {v.get("value") for v in included["values"]}
                values = [v for v in values if v.get("value") in names]
        for statements in self.rules(definition):
            if not statements or any(s.get("isSelectable") is False for s in statements):
                return []
            names = {s.get("value") for s in statements if s.get("value", "").startswith(definition["key"] + ".")}
            if names:
                values = [v for v in values if v.get("value") in names]
        return values

    def limits(self, definition):
        limits = dict(definition.get("valueLimits") or {})
        # Official app's help explicitly allows a 30-minute quick-off timer;
        # the discovery hour minimum of 1 would wrongly reject hour=0.
        if definition["key"] == "Climate.AirConditioner.Setting.QuickOffTime.Hour":
            limits["min"] = 0
        included = self.context(definition)
        if included:
            limits.update(included.get("valueLimits") or {})
        for statements in self.rules(definition):
            for s in statements:
                limits.update(s.get("valueLimits") or {})
        return limits

    def validate(self, definition, value=None):
        key = definition["key"]
        if not self.read_ok or self.metadata.get("connected") is False:
            raise SchemaError('status_unavailable')
        if key.endswith((".Command.UvonOn", ".Command.UvonOff")):
            self.expected_registers([], command=key)
        if self.family in {"DW", "WD"}:
            remote = (self.status(".RemoteControlOn") if self.family == "WD"
                      else str(self.status(".RemoteControl") or "").endswith(".Open"))
            if not remote:
                raise SchemaError('remote_required')
            state = str(self.status(".ExecutionState") or "").rsplit(".", 1)[-1]
            idle = {"Selection", "PreProgram", "End", "EndMode"}
            if ".Program." in key and state not in {"Selection", "PreProgram"}:
                raise SchemaError('return_to_selection')
            if self.family == "WD" and self.status(".Standby") is True and (
                ".Program." in key or ".Option." in key or key.endswith(".Command.Start")
            ):
                raise SchemaError('wake_appliance')
            for field, suffix in (("supportedStates", ".ExecutionState"), ("supportedPhases", ".StepInfo")):
                supported = definition.get(field)
                if supported and (field != "supportedPhases" or state not in idle):
                    if self.status(suffix) not in {v.get("key") for v in supported}:
                        raise SchemaError('unsupported_phase')
            if key.endswith(".Command.Start") and state not in idle | {"Pause", "InDelayPause"}:
                raise SchemaError('not_ready_to_start')
            if key.endswith(".Command.Pause") and state not in {"Running", "Program", "InDelay"}:
                raise SchemaError('not_running')
        included = self.context(definition)
        if included is not None and (not included or included.get("isSelectable") is False):
            raise SchemaError('feature_unavailable')
        for statements in self.rules(definition):
            if not statements or any(s.get("isSelectable") is False for s in statements):
                raise SchemaError('incompatible_option')
        if value is None:
            return
        integer(value)
        if ".Program." in key and value != definition.get("commandValue"):
            raise SchemaError('program_value_invalid')
        if definition.get("valueType") == "Boolean" and value not in (0, definition.get("commandValue", 1)):
            raise SchemaError('boolean_invalid')
        if definition.get("values"):
            if value not in {v["commandValue"] for v in self.values(definition)}:
                raise SchemaError('value_unavailable')
        if self.family == "WD" and value and key.endswith((".Option.Dry", ".Option.TimeDry")):
            other_suffix = ".Option.TimeDry" if key.endswith(".Option.Dry") else ".Option.Dry"
            other = self.find_suffix(other_suffix, "options")
            if other and Field(other).raw(self.registers):
                raise SchemaError('dry_conflict')
        limits = self.limits(definition)
        if limits:
            if value < limits.get("min", value) or value > limits.get("max", value):
                raise SchemaError('out_of_range')
            step = limits.get("step", 1) or 1
            if (value - limits.get("min", 0)) % step:
                raise SchemaError('invalid_step')

    def encode(self, definition, value):
        self.validate(definition, value)
        if definition.get("key") == "Climate.AirConditioner.Setting.Temperature":
            value -= definition["commandValue"]
        return Field(definition).replace_bits(self.registers, value)

    def incompatible_booleans(self, definition, value):
        """Fields automatically cleared when enabling an incompatible toggle."""
        if definition.get("valueType") == "Boolean" and value == 1:
            for incompatible in definition.get("incompatibleSettings", []) + definition.get("incompatibleOptions", []):
                other = self.find(incompatible.get("key"))
                if other and other.get("valueType") == "Boolean":
                    yield other

    def build(self, updates):
        """Merge fields sharing one register into a single command."""
        working = dict(self.registers)
        touched = []
        for key, value in updates:
            definition = next((d for d in self.definitions("settings", "options", "programs") if d.get("key") == key), None)
            if definition is None:
                raise SchemaError('not_writable')
            temporary = Device(self.metadata, self.discovery, working, self.read_ok)
            # Apply discovery's incompatible-setting/option rules before
            # enabling the toggle. Preserve every unrelated register bit.
            for other in self.incompatible_booleans(definition, value):
                code = Field(other).replace_bits(working, 0)
                working[code[:7]] = code[7:]
                if code[:7] not in touched:
                    touched.append(code[:7])
            code = temporary.encode(definition, value)
            working[code[:7]] = code[7:]
            if code[:7] not in touched:
                touched.append(code[:7])
        return [command + f"{integer(working[command]):05d}" for command in touched]

    def command(self, key):
        definition = self.find(key)
        if not definition or ".Command." not in key:
            raise SchemaError('command_unsupported')
        self.validate(definition)
        value = integer(definition.get("commandValue"))
        layout = Field(definition).layout()
        if layout:
            position, length = layout
            if value >= 1 << length and value % (1 << position) == 0:
                # AC AutoOn.Cancel is returned already shifted by the cloud.
                value >>= position
        return Field(definition).replace_bits(self.registers, value)

    def expected_registers(self, codes, *, command=None):
        """A command opcode need not equal the resulting status value.

        Discovery provides separate UV write opcodes and SettingIndex states.
        Match the requested state name; never mistake an opcode echo for success.
        """
        result = {code[:7]: int(code[7:]) for code in codes}
        if command and command.endswith((".Command.UvonOn", ".Command.UvonOff")):
            definition = self.find(command)
            status = self.find_suffix(".Status.SettingIndex", "status")
            name = command.rsplit(".", 1)[-1]
            value = next((v.get("commandValue") for v in (status or {}).get("values", [])
                          if v.get("value", "").rsplit(".", 1)[-1] == name), None)
            if (self.family != "DW" or not definition or not status or type(value) is not int
                    or definition.get("commandName") != status.get("commandName")):
                raise SchemaError('uv_result_missing')
            code = Field(status).replace_bits(self.registers, value)
            result = {code[:7]: int(code[7:])}
        return result

    def expected_readback(self, codes, *, updates=None, command=None) -> Readback:
        """Verify targeted fields, including automatic incompatible resets.

        Use the final merged values for fields sharing a register. Commands
        without a bit layout still require a full register match, and UV
        commands retain their explicit result-state mapping.
        """
        values = self.expected_registers(codes, command=command)
        definitions = []
        if command:
            definition = (self.find_suffix(".Status.SettingIndex", "status")
                          if command.endswith((".Command.UvonOn", ".Command.UvonOff"))
                          else self.find(command))
            definitions.append(definition)
        else:
            for key, value in updates or []:
                definition = self.find(key)
                if definition is None:
                    raise SchemaError('readback_definition_missing')
                definitions.append(definition)
                definitions.extend(self.incompatible_booleans(definition, value))
        masks = {}
        for definition in definitions:
            if definition is None:
                raise SchemaError('readback_definition_missing')
            field = Field(definition)
            layout = field.layout()
            mask = ((1 << layout[1]) - 1) << layout[0] if layout else 65535
            masks[field.command] = masks.get(field.command, 0) | mask
        if set(masks) != set(values):
            raise SchemaError('readback_fields_missing')
        return Readback(values, masks)
