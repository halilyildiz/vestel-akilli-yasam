"""Registry defaults and adapter identity tests using minimal HA metadata stubs.

The real Home Assistant runtime is additionally checked after deployment.
"""

from __future__ import annotations
import json
import sys
import types
import unittest
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import test_coordinator  # noqa: F401 -- initialize the shared HA/HTTP test runtime.


def module(name: str) -> types.ModuleType:
    return sys.modules.setdefault(name, types.ModuleType(name))


class EntityCategory(StrEnum):
    DIAGNOSTIC = "diagnostic"
    CONFIG = "config"


class SensorDeviceClass(StrEnum):
    TEMPERATURE = "temperature"
    ENERGY = "energy"
    SIGNAL_STRENGTH = "signal_strength"
    DURATION = "duration"


class BinarySensorDeviceClass(StrEnum):
    DOOR = "door"
    PROBLEM = "problem"
    CONNECTIVITY = "connectivity"


@dataclass(frozen=True, kw_only=True)
class EntityDescription:
    key: str
    name: str | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    device_class: str | None = None
    native_unit_of_measurement: str | None = None


class Entity:
    # The documented HA resolution order: explicit _attr overrides description.
    @property
    def entity_category(self) -> EntityCategory | None:
        if hasattr(self, "_attr_entity_category"):
            return self._attr_entity_category
        return self.entity_description.entity_category

    @property
    def entity_registry_enabled_default(self) -> bool:
        if hasattr(self, "_attr_entity_registry_enabled_default"):
            return self._attr_entity_registry_enabled_default
        return self.entity_description.entity_registry_enabled_default


class CoordinatorEntity(Entity):
    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        return True


module("homeassistant.components")
module("homeassistant.components.sensor").SensorEntity = type(
    "SensorEntity", (Entity,), {}
)
module("homeassistant.components.sensor").SensorEntityDescription = EntityDescription
module("homeassistant.components.sensor").SensorDeviceClass = SensorDeviceClass
module("homeassistant.components.binary_sensor").BinarySensorEntity = type(
    "BinarySensorEntity", (Entity,), {}
)
module(
    "homeassistant.components.binary_sensor"
).BinarySensorEntityDescription = EntityDescription
module(
    "homeassistant.components.binary_sensor"
).BinarySensorDeviceClass = BinarySensorDeviceClass
module("homeassistant.const").EntityCategory = EntityCategory
module("homeassistant.const").UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
module("homeassistant.helpers.entity").EntityDescription = EntityDescription
module("homeassistant.helpers.entity").DeviceInfo = dict
module("homeassistant.helpers.typing").StateType = str | int | float | None
module("homeassistant.helpers.update_coordinator").CoordinatorEntity = CoordinatorEntity

from custom_components.vestel_appliances.entity_descriptions import (
    DOOR_DESCRIPTION,
    METRICS,
    PERIODS,
    PROBLEM_DESCRIPTION,
    binary_description,
    consumption_description,
    control_description,
    entity_policy,
    sensor_description,
)
from custom_components.vestel_appliances.sensor import (
    Status as ScalarStatus,
    Consumption,
)
from custom_components.vestel_appliances.binary_sensor import (
    Status as BinaryStatus,
    RefrigeratorDoor,
    LiveConnection,
    Problem,
)
from custom_components.vestel_appliances.entity import Control
from custom_components.vestel_appliances.protocol import Device


class DescriptionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/device-snapshot.json").read_text()
        )
        self.devices = {
            d["metadata"]["deviceType"]: Device(
                d["metadata"], d["discovery"], d["registers"]
            )
            for d in fixture["devices"]
        }
        self.coordinator = types.SimpleNamespace(
            data=self.devices,
            last_commands={},
            live=types.SimpleNamespace(
                connected=True, subscribed_devices=set(self.devices), stats={}
            ),
        )

    def test_technical_scalar_metrics_are_disabled_diagnostic(self) -> None:
        suffixes = (
            "Wifi.SignalRSS",
            "Connection.SignalRSS",
            "SoftwareInfo.Name",
            "SoftwareInfo.Version",
            "Uptime",
            "RuntimeSeconds",
            "ErrorCount",
            "TotalErrorCounter",
            "LinkQuality",
            "FirmwareVersion",
        )
        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                desc = sensor_description({"key": "Device.Status." + suffix})
                self.assertEqual(desc.entity_category, EntityCategory.DIAGNOSTIC)
                self.assertFalse(desc.entity_registry_enabled_default)

    def test_program_duration_is_not_confused_with_technical_uptime(self) -> None:
        for suffix in (
            "RemainingDuration",
            "ProgramDuration",
            "Duration",
            "RemainingDelayDuration",
            "ProgramPhase",
            "ExecutionState",
            "SelectedProgram",
            "RoomTemperature",
        ):
            with self.subTest(suffix=suffix):
                desc = sensor_description({"key": "Device.Status." + suffix})
                self.assertIsNone(desc.entity_category)
                self.assertTrue(desc.entity_registry_enabled_default)

    def test_all_real_firmware_wifi_and_connection_descriptions_are_optional(
        self,
    ) -> None:
        checked = 0
        for device in self.devices.values():
            for definition in device.definitions("status"):
                if any(
                    part in definition["key"]
                    for part in ("SoftwareInfo", ".Wifi", ".Connection")
                ):
                    desc = sensor_description(definition)
                    self.assertFalse(desc.entity_registry_enabled_default)
                    self.assertEqual(desc.entity_category, EntityCategory.DIAGNOSTIC)
                    checked += 1
        self.assertGreater(checked, 5)

    def test_detailed_fault_flags_are_optional_but_general_problem_is_primary(
        self,
    ) -> None:
        for device in self.devices.values():
            for definition in device.definitions("errors"):
                desc = binary_description(definition)
                self.assertFalse(desc.entity_registry_enabled_default)
                self.assertEqual(desc.entity_category, EntityCategory.DIAGNOSTIC)
        self.assertTrue(PROBLEM_DESCRIPTION.entity_registry_enabled_default)
        self.assertIsNone(PROBLEM_DESCRIPTION.entity_category)

    def test_raw_door_is_optional_while_user_door_sensor_is_primary(self) -> None:
        raw = sensor_description({"key": "Refrigeration.Refrigerator.Status.Door"})
        self.assertFalse(raw.entity_registry_enabled_default)
        self.assertEqual(raw.entity_category, EntityCategory.DIAGNOSTIC)
        self.assertTrue(DOOR_DESCRIPTION.entity_registry_enabled_default)
        self.assertIsNone(DOOR_DESCRIPTION.entity_category)

    def test_writable_calibration_is_config_but_read_only_calibration_is_diagnostic(
        self,
    ) -> None:
        desc = control_description({"key": "Device.Setting.VoltageCalibration"})
        self.assertEqual(desc.entity_category, EntityCategory.CONFIG)
        self.assertFalse(desc.entity_registry_enabled_default)
        self.assertEqual(
            entity_policy("Device.Status.VoltageCalibration").category,
            EntityCategory.DIAGNOSTIC,
        )

    def test_basic_controls_and_preference_config_defaults(self) -> None:
        for suffix in ("Mode", "Temperature"):
            desc = control_description({"key": "Device.Setting." + suffix})
            self.assertTrue(desc.entity_registry_enabled_default)
            self.assertIsNone(desc.entity_category)
        desc = control_description({"key": "Device.Setting.ScreenSaver"})
        self.assertTrue(desc.entity_registry_enabled_default)
        self.assertEqual(desc.entity_category, EntityCategory.CONFIG)

    def test_consumption_estimates_are_optional_uncategorized_and_identity_compatible(
        self,
    ) -> None:
        for period in PERIODS:
            for metric in METRICS:
                desc = consumption_description(period, metric)
                self.assertFalse(desc.entity_registry_enabled_default)
                self.assertIsNone(desc.entity_category)
                self.assertEqual(desc.key, f"consumption_{period}_{metric}")
                self.assertIn("tahmini", desc.name)

    def test_signal_unit_is_never_invented(self) -> None:
        definition = {
            "key": "Device.Status.Wifi.SignalRSS",
            "valueLimits": {"min": 0, "max": 100, "unit": ""},
        }
        desc = sensor_description(definition)
        self.assertIsNone(desc.native_unit_of_measurement)
        self.assertIsNone(desc.device_class)
        definition["valueLimits"]["unit"] = "dBm"
        self.assertEqual(
            sensor_description(definition).device_class,
            SensorDeviceClass.SIGNAL_STRENGTH,
        )

    def test_runtime_sensor_instances_honor_description_without_attr_shadowing(
        self,
    ) -> None:
        device = self.devices["AC"]
        technical = device.find_suffix(".Status.SoftwareInfo.Version", "status")
        entity = ScalarStatus(self.coordinator, "AC", technical)
        self.assertFalse(entity.entity_registry_enabled_default)
        self.assertEqual(entity.entity_category, EntityCategory.DIAGNOSTIC)
        self.assertEqual(entity._attr_unique_id, "AC_" + technical["key"])
        primary = ScalarStatus(
            self.coordinator,
            "AC",
            device.find_suffix(".Status.RoomTemperature", "status"),
        )
        self.assertTrue(primary.entity_registry_enabled_default)
        self.assertIsNone(primary.entity_category)

    def test_binary_instances_preserve_ids_and_primary_vs_optional_defaults(
        self,
    ) -> None:
        for entity, key, enabled in (
            (LiveConnection(self.coordinator, "RF"), "live_connection", False),
            (RefrigeratorDoor(self.coordinator, "RF"), "door_open", True),
            (Problem(self.coordinator, "RF"), "problem", True),
        ):
            self.assertEqual(entity._attr_unique_id, "RF_" + key)
            self.assertEqual(entity.entity_registry_enabled_default, enabled)
        definition = self.devices["AC"].find_suffix(".Error.GasLeakageError", "errors")
        fault = BinaryStatus(self.coordinator, "AC", definition)
        self.assertFalse(fault.entity_registry_enabled_default)
        self.assertEqual(fault.entity_category, EntityCategory.DIAGNOSTIC)

    def test_consumption_runtime_entities_and_controls_use_metadata(self) -> None:
        energy = types.SimpleNamespace(data={}, billing=None)
        entity = Consumption(energy, "AC", "month", "energyAmount")
        self.assertEqual(entity._attr_unique_id, "AC_consumption_month_energyAmount")
        self.assertFalse(entity.entity_registry_enabled_default)
        self.assertIsNone(entity.entity_category)
        technical_control = Control(
            self.coordinator, "RF", {"key": "Device.Setting.VoltageCalibration"}
        )
        self.assertFalse(technical_control.entity_registry_enabled_default)
        self.assertEqual(technical_control.entity_category, EntityCategory.CONFIG)


if __name__ == "__main__":
    unittest.main()
