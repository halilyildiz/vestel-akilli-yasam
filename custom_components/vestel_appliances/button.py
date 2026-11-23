from homeassistant.components.button import ButtonEntity
from .dynamic import setup_dynamic_entities
from .entity import Control


async def async_setup_entry(hass, entry, add):
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c, uuid, state):
    entities = []
    for d in state.definitions("commands"):
        button = Action(c, uuid, d)
        if d["key"].endswith((".InDelay", ".IonizerInProgress", ".UvonOn", ".UvonOff")):
            button._attr_entity_registry_enabled_default = False
        entities.append(button)
    return entities


class Action(Control, ButtonEntity):
    async def async_press(self):
        await self.coordinator.apply(self.uuid, command=self.key)
