from homeassistant.components.switch import SwitchEntity
from .dynamic import setup_dynamic_entities
from .entity import Control


async def async_setup_entry(hass, entry, add):
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c, uuid, state):
    if not state.writable:
        return []
    entities = [Toggle(c, uuid, d) for d in state.definitions("settings", "options") if d.get("valueType") == "Boolean"]
    if state.family == "DW" and (d := state.find_suffix(".Command.UvonOn", "commands")) and state.find_suffix(".Command.UvonOff", "commands"):
        entities.append(Ultraviolet(c, uuid, d))
    return entities


class Toggle(Control, SwitchEntity):
    @property
    def is_on(self):
        return self.state_data.decode(self.definition)

    async def async_turn_on(self, **kwargs):
        await self.write(self.definition.get("commandValue", 1))

    async def async_turn_off(self, **kwargs):
        await self.write(0)


class Ultraviolet(Control, SwitchEntity):
    @property
    def is_on(self):
        name = str(self.state_data.status(".SettingIndex") or "").rsplit(".", 1)[-1]
        return {"UvonOn": True, "UvonOff": False}.get(name)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.apply(self.uuid, command=self.key)

    async def async_turn_off(self, **kwargs):
        definition = self.state_data.find_suffix(".Command.UvonOff", "commands")
        await self.coordinator.apply(self.uuid, command=definition["key"])
