"""Primary appliance state and optional technical fault/connectivity detail."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity

from .dynamic import setup_dynamic_entities
from .entity import Base
from .entity_descriptions import (
    DOOR_DESCRIPTION,
    LIVE_CONNECTION_DESCRIPTION,
    PROBLEM_DESCRIPTION,
    binary_description,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import Coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c: Coordinator, uuid: str, state) -> list:
    entities = [LiveConnection(c, uuid)]
    if state.family == "RF" and state.find_suffix(".Status.Door", "status"):
        entities.append(RefrigeratorDoor(c, uuid))
    for definition in state.definitions("status", "errors"):
        if definition.get("valueType") != "Boolean" or definition["key"].endswith(("Off", "Closed", ".NoError")):
            continue
        entities.append(Status(c, uuid, definition))
    if state.discovery.get("errors"):
        entities.append(Problem(c, uuid))
    return entities


class Status(Base, BinarySensorEntity):
    def __init__(
        self, coordinator: Coordinator, uuid: str, definition: dict[str, Any]
    ) -> None:
        super().__init__(
            coordinator, uuid, definition, description=binary_description(definition)
        )

    @property
    def is_on(self) -> bool | None:
        return self.state_data.decode(self.definition)


class LiveConnection(Base, BinarySensorEntity):
    def __init__(self, coordinator: Coordinator, uuid: str) -> None:
        super().__init__(
            coordinator,
            uuid,
            {"key": LIVE_CONNECTION_DESCRIPTION.key},
            description=LIVE_CONNECTION_DESCRIPTION,
        )

    @property
    def is_on(self) -> bool:
        return (
            self.coordinator.live.connected
            and self.uuid in self.coordinator.live.subscribed_devices
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**super().extra_state_attributes, **self.coordinator.live.stats}


class RefrigeratorDoor(Base, BinarySensorEntity):
    def __init__(self, coordinator: Coordinator, uuid: str) -> None:
        super().__init__(
            coordinator,
            uuid,
            {"key": DOOR_DESCRIPTION.key},
            description=DOOR_DESCRIPTION,
        )

    @property
    def is_on(self) -> bool | None:
        return self.state_data.refrigerator_door_open()


class Problem(Base, BinarySensorEntity):
    def __init__(self, coordinator: Coordinator, uuid: str) -> None:
        super().__init__(
            coordinator,
            uuid,
            {"key": PROBLEM_DESCRIPTION.key},
            description=PROBLEM_DESCRIPTION,
        )

    @property
    def is_on(self) -> bool | None:
        commands = {
            d["commandName"]
            for d in self.state_data.discovery.get("errors", [])
            if d.get("commandName")
        }
        values = [self.state_data.registers.get(key) for key in commands]
        known = [
            int(value)
            for value in values
            if isinstance(value, (str, int)) and str(value).isdecimal()
        ]
        if any(value != 0 for value in known):
            return True
        return False if len(known) == len(commands) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = super().extra_state_attributes
        state = (self.coordinator.data or {}).get(self.uuid)
        if state is None:
            return {**result, "error_registers": {}}
        commands = {
            d["commandName"]
            for d in state.discovery.get("errors", [])
            if d.get("commandName")
        }
        result["error_registers"] = {
            key: state.registers.get(key) for key in commands
        }
        return result
