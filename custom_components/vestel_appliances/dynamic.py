"""Add entities for newly discovered devices and firmware descriptions."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from .entity import coordinator_for
from .fields import SchemaError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from .coordinator import Coordinator
    from .protocol import Device


def setup_dynamic_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add: AddEntitiesCallback,
    factory: Callable[[Coordinator, str, Device], Iterable[Entity]],
) -> None:
    coordinator = coordinator_for(hass, entry)
    seen: dict[str, Entity] = {}
    descriptions: dict[str, Any] = {}

    def discover() -> None:
        entities: list[Entity] = []
        for uuid, state in (coordinator.data or {}).items():
            if not state.discovery or descriptions.get(uuid) is state.discovery:
                continue
            try:
                candidates = list(factory(coordinator, uuid, state))
            except (SchemaError, KeyError, TypeError, ValueError, AttributeError):
                # One unknown model cannot abort other devices' entity setup.
                coordinator.set_platform_error(uuid, factory.__module__, True)
                continue
            coordinator.set_platform_error(uuid, factory.__module__, False)
            descriptions[uuid] = state.discovery
            for entity in candidates:
                unique_id = entity._attr_unique_id
                if unique_id not in seen:
                    seen[unique_id] = entity
                    entities.append(entity)
                else:
                    # Same registry identity, refreshed schema after firmware
                    # change. Do not leave existing entities decoding old bits.
                    current = seen[unique_id]
                    for name in ("definition", "minute", "entity_description",
                                 "_attr_supported_features", "_attr_device_info"):
                        if hasattr(entity, name):
                            setattr(current, name, getattr(entity, name))
        if entities:
            add(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
