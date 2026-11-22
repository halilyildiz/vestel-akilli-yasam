"""Primary and optional diagnostic sensors described using HA metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, choice
from .energy import sample_value
from .dynamic import setup_dynamic_entities
from .entity import Base
from .entity_descriptions import (
    METRICS,
    PERIODS,
    Metric,
    Period,
    consumption_description,
    sensor_description,
)
from .fields import Field, SchemaError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import Coordinator
    from .energy import EnergyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c: Coordinator, uuid: str, state) -> list:
    entities = [Status(c, uuid, d) for d in state.definitions("status") if d.get("valueType") != "Boolean"]
    for period in PERIODS:
        for metric in METRICS:
            entities.append(Consumption(c.energy, uuid, period, metric))
    return entities


class Status(Base, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(
        self, coordinator: Coordinator, uuid: str, definition: dict[str, Any]
    ) -> None:
        super().__init__(
            coordinator, uuid, definition, description=sensor_description(definition)
        )

    @property
    def native_value(self) -> StateType:
        if self.key.endswith(".Status.Door"):
            try:
                return Field(self.definition).raw(self.state_data.registers)
            except SchemaError:
                return None
        value = self.state_data.decode(self.definition)
        return choice(value) if isinstance(value, str) else value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        attrs["register"] = self.definition.get("commandName")
        if self.key.endswith(".Status.Door"):
            attrs["interpretation"] = "APK: 3=kapalı, 0/1/2=en az bir kapı açık"
        return attrs


class Consumption(CoordinatorEntity, SensorEntity):
    """Optional period estimates; never presented as cumulative meter totals."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self, coordinator: EnergyCoordinator, uuid: str, period: Period, metric: Metric
    ) -> None:
        super().__init__(coordinator)
        self.uuid, self.period, self.metric = uuid, period, metric
        self.entity_description = consumption_description(period, metric)
        # Preserve the existing unique IDs and registry entries on upgrade.
        self._attr_unique_id = f"{uuid}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, uuid)})

    @property
    def history(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self.uuid, {}).get(self.period)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.history is not None
            and self.native_value is not None
        )

    @property
    def native_value(self) -> StateType:
        return sample_value(self.history, self.metric)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.metric == "energyCost":
            billing = self.coordinator.billing or {}
            return (self.history or {}).get("currencyShortCode") or billing.get(
                "home", {}
            ).get("currencyShortCode")
        # The service does not specify a water unit; no conversion is guessed.
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        samples = (self.history or {}).get("samples") or []
        return {
            "estimated": True,
            "period": self.period,
            "period_date": samples[0].get("date") if samples else None,
            "source": "Vestel Akıllı Yaşam tüketim geçmişi",
        }
