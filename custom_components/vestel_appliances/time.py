from datetime import time
from homeassistant.components.time import TimeEntity
from .dynamic import setup_dynamic_entities
from .entity import Control


async def async_setup_entry(hass, entry, add):
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c, uuid, state):
    entities = []
    if state.family == "AC":
        for name, label in (("AutoOn", "Otomatik açılma saati"), ("AutoOff", "Otomatik kapanma saati")):
            hour = state.find_suffix(".Setting." + name + ".Hour", "settings")
            minute = state.find_suffix(".Setting." + name + ".Minute", "settings")
            if hour and minute:
                entity = Timer(c, uuid, hour)
                entity.minute = minute
                entity._attr_name = label
                entities.append(entity)
    return entities


class Timer(Control, TimeEntity):
    @property
    def native_value(self):
        hour = self.state_data.decode(self.definition)
        minute = self.state_data.decode(self.minute)
        if isinstance(hour, int) and isinstance(minute, int) and 0 <= hour < 24 and 0 <= minute < 60:
            return time(hour, minute)
        return None

    async def async_set_value(self, value):
        await self.coordinator.apply(self.uuid, updates=[(self.key, value.hour), (self.minute["key"], value.minute)])
