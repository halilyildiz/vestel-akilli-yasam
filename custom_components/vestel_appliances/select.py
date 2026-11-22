from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from .dynamic import setup_dynamic_entities
from .entity import Control
from .const import choice


async def async_setup_entry(hass, entry, add):
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c, uuid, state):
    entities = []
    for d in state.definitions("settings", "options"):
        if d.get("valueType") != "Enum" or state.family == "AC" and d["key"].endswith((".Mode", ".Speed")):
            continue
        entities.append(Setting(c, uuid, d))
    programs = [p for p in state.discovery.get("programs", []) if not p["key"].endswith(".Reset")]
    if programs:
        entity = Program(c, uuid, {"key": "program", "programs": programs})
        entity._attr_name = "Program"
        entities.append(entity)
    return entities


class Setting(Control, SelectEntity):
    @property
    def options(self):
        return [choice(v["value"]) for v in self.state_data.values(self.definition)]

    @property
    def current_option(self):
        value = self.state_data.decode(self.definition)
        return choice(value) if value else None

    async def async_select_option(self, option):
        value = next((v for v in self.state_data.values(self.definition) if choice(v["value"]) == option), None)
        if value is None:
            raise HomeAssistantError("Bu seçenek mevcut mod/programda kullanılamıyor.")
        await self.write(value["commandValue"])


class Program(Control, SelectEntity):
    _attr_name = "Program"

    @property
    def options(self):
        return [choice(p["key"]) for p in self.definition["programs"]]

    @property
    def available(self):
        if not super().available:
            return False
        return self.state_data.status(".Standby") is not True and str(self.state_data.status(".ExecutionState") or "").rsplit(".", 1)[-1] in {"Selection", "PreProgram"}

    @property
    def current_option(self):
        current = self.state_data.status(".SelectedProgram")
        return choice(current) if current else None

    async def async_select_option(self, option):
        program = next((p for p in self.definition["programs"] if choice(p["key"]) == option), None)
        if program is None:
            raise HomeAssistantError("Program bulunamadı.")
        await self.coordinator.apply(self.uuid, updates=[(program["key"], program["commandValue"])])
