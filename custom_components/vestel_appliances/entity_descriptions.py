"""Home Assistant presentation metadata, independent of cloud/register logic."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.helpers.entity import EntityDescription

from .const import label

Period = Literal["day", "month"]
Metric = Literal["energyAmount", "energyCost", "water"]
PERIODS: Final[tuple[Period, ...]] = ("day", "month")
METRICS: Final[tuple[Metric, ...]] = ("energyAmount", "energyCost", "water")

_TECHNICAL_SEGMENTS: Final = frozenset(
    {
        "softwareinfo",
        "hardwareinfo",
        "wifi",
        "network",
        "connection",
        "diagnostic",
        "diagnostics",
        "debug",
        "calibration",
    }
)
_TECHNICAL_LEAVES: Final = frozenset(
    {
        "wifisetting",
        "signalrss",
        "signalstrength",
        "linkquality",
        "lqi",
        "rssi",
        "uptime",
        "uptimeseconds",
        "totaluptime",
        "runtime",
        "totalruntime",
        "operatinghours",
        "maxmachinespin",
        "settingindex",
        "supplyvoltage",
        "mainsvoltage",
        "voltage",
    }
)
_RAW_DOOR_SUFFIX: Final = ".Status.Door"
_PREFERENCE_SUFFIXES: Final = (".Setting.ScreenSaver", ".Setting.ChildLock")


@dataclass(frozen=True, kw_only=True)
class EntityPolicy:
    """Registry defaults; existing user registry choices are never migrated."""

    category: EntityCategory | None = None
    enabled_default: bool = True


def entity_policy(key: str, *, writable: bool = False) -> EntityPolicy:
    """Classify purpose, not just unit or a broad word such as 'duration'."""
    segments = frozenset(part.casefold() for part in key.split("."))
    leaf = key.rsplit(".", 1)[-1].casefold().replace("_", "")
    technical = bool(segments & _TECHNICAL_SEGMENTS) or leaf in _TECHNICAL_LEAVES
    technical |= any(
        marker in leaf
        for marker in ("firmware", "version", "calibration", "uptime", "rssi", "lqi")
    )
    technical |= leaf.startswith(("runtime", "totalruntime", "operatinghours"))
    technical |= any(
        marker in leaf
        for marker in ("errorcount", "errorcounter", "faultcount", "faultcounter")
    )
    technical |= leaf.endswith(("count", "counter")) and any(
        marker in leaf
        for marker in ("error", "fault", "disconnect", "reboot", "restart")
    )
    technical |= ".Error." in key or key.endswith(
        (_RAW_DOOR_SUFFIX, ".Status.ScreenSaver")
    )
    technical |= ".Setting.Clock." in key
    if technical:
        return EntityPolicy(
            category=EntityCategory.CONFIG if writable else EntityCategory.DIAGNOSTIC,
            enabled_default=False,
        )
    if writable and key.endswith(_PREFERENCE_SUFFIXES):
        return EntityPolicy(category=EntityCategory.CONFIG, enabled_default=True)
    return EntityPolicy()


def sensor_description(definition: Mapping[str, Any]) -> SensorEntityDescription:
    """Convert cloud discovery to HA metadata without changing unique IDs."""
    key = str(definition["key"])
    policy = entity_policy(key)
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    name = "Kapı ham kodu" if key.endswith(_RAW_DOOR_SUFFIX) else label(key)
    if key.endswith((".RemainingDuration", ".Duration", ".ProgramDuration")):
        unit = "min"
    elif key.endswith(".RoomTemperature"):
        unit, device_class = UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE
    elif policy.category == EntityCategory.DIAGNOSTIC:
        # SignalRSS values on current devices are positive raw codes, not dBm.
        # Assign a signal unit/class only when discovery explicitly supplies it.
        declared_unit = (definition.get("valueLimits") or {}).get("unit")
        if declared_unit == "dBm":
            unit, device_class = "dBm", SensorDeviceClass.SIGNAL_STRENGTH
        elif "uptime" in key.casefold() and declared_unit in {"second", "seconds", "s"}:
            unit, device_class = "s", SensorDeviceClass.DURATION
    return SensorEntityDescription(
        key=key,
        name=name,
        entity_category=policy.category,
        entity_registry_enabled_default=policy.enabled_default,
        native_unit_of_measurement=unit,
        device_class=device_class,
    )


def binary_description(definition: Mapping[str, Any]) -> BinarySensorEntityDescription:
    key = str(definition["key"])
    policy = entity_policy(key)
    return BinarySensorEntityDescription(
        key=key,
        name=label(key),
        entity_category=policy.category,
        entity_registry_enabled_default=policy.enabled_default,
    )


def control_description(definition: Mapping[str, Any]) -> EntityDescription:
    key = str(definition["key"])
    policy = entity_policy(key, writable=True)
    return EntityDescription(
        key=key,
        name=label(key),
        entity_category=policy.category,
        entity_registry_enabled_default=policy.enabled_default,
    )


def consumption_description(period: Period, metric: Metric) -> SensorEntityDescription:
    period_name = {"day": "Günlük", "month": "Aylık"}[period]
    metric_name = {
        "energyAmount": "tahmini enerji",
        "energyCost": "tahmini maliyet",
        "water": "tahmini su tüketimi",
    }[metric]
    return SensorEntityDescription(
        key=f"consumption_{period}_{metric}",
        name=f"{period_name} {metric_name}",
        entity_category=None,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENERGY if metric == "energyAmount" else None,
        native_unit_of_measurement="kWh" if metric == "energyAmount" else None,
    )


LIVE_CONNECTION_DESCRIPTION: Final = BinarySensorEntityDescription(
    key="live_connection",
    name="Canlı veri bağlantısı",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)
DOOR_DESCRIPTION: Final = BinarySensorEntityDescription(
    key="door_open",
    name="Kapı açık",
    device_class=BinarySensorDeviceClass.DOOR,
    entity_category=None,
    entity_registry_enabled_default=True,
)
PROBLEM_DESCRIPTION: Final = BinarySensorEntityDescription(
    key="problem",
    name="Arıza",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=None,
    entity_registry_enabled_default=True,
)
