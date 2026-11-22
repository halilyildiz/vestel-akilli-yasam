from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, label
from .entity_descriptions import control_description
from .fields import SchemaError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import Coordinator
    from .protocol import Device


class Base(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Coordinator,
        uuid: str,
        definition: dict[str, Any],
        suffix: str = "",
        *,
        description: EntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.uuid, self.definition = uuid, definition
        self.key = definition["key"]
        self._attr_unique_id = uuid + "_" + self.key + suffix
        self._attr_name = label(self.key)
        if description is not None:
            self.entity_description = description
            if isinstance(description.name, str) or description.name is None:
                self._attr_name = description.name
        state = self.state_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uuid)},
            manufacturer="Vestel",
            name=state.metadata.get("deviceName") or state.family,
            model=state.metadata.get("variant") or state.metadata.get("deviceModel"),
            sw_version=state.metadata.get("wifiVersion"),
        )

    @property
    def state_data(self) -> Device:
        return self.coordinator.data[self.uuid]

    @property
    def available(self) -> bool:
        state = (self.coordinator.data or {}).get(self.uuid)
        if state is not None:
            if "." in self.key and state.find(self.key) is None:
                return False
            if self.key == "program" and not state.discovery.get("programs"):
                return False
            if self.key == "climate" and (not state.find_suffix(".Setting.Mode", "settings") or not state.find_suffix(".Setting.Temperature", "settings")):
                return False
        return (
            super().available
            and state is not None
            and state.read_ok
            and state.metadata.get("connected") is not False
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "vestel_key": self.key,
            "last_command": self.coordinator.last_commands.get(self.uuid),
        }

    async def write(self, value: int) -> dict[str, Any]:
        return await self.coordinator.apply(self.uuid, updates=[(self.key, value)])


class Control(Base):
    def __init__(
        self,
        coordinator: Coordinator,
        uuid: str,
        definition: dict[str, Any],
        suffix: str = "",
    ) -> None:
        super().__init__(
            coordinator,
            uuid,
            definition,
            suffix,
            description=control_description(definition),
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        try:
            self.state_data.validate(self.definition)
            return True
        except SchemaError:
            return False


def coordinator_for(hass: HomeAssistant, entry: ConfigEntry) -> Coordinator:
    return hass.data[DOMAIN][entry.entry_id]
