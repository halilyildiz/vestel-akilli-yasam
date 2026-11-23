from homeassistant.components.number import NumberEntity, NumberMode
from .errors import user_error
from .dynamic import setup_dynamic_entities
from .entity import Control


async def async_setup_entry(hass, entry, add):
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c, uuid, state):
    if not state.writable:
        return []
    entities = [SettingNumber(c, uuid, d) for d in state.definitions("options") if d.get("valueType") in {"Integer", "Number"}]
    if state.family == "AC":
        d = state.find_suffix(".Setting.QuickOffTime.Hour", "settings")
        if d and state.find_suffix(".Setting.QuickOffTime.Minute", "settings"):
            entity = QuickOff(c, uuid, d, "_duration")
            entities.append(entity)
    return entities


class SettingNumber(Control, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, *args):
        super().__init__(*args)
        # WD delay's option range/step are minutes even though a separate
        # status definition labels the same register as hours.
        self._attr_native_unit_of_measurement = "min" if self.key.endswith((".Delay", ".DelayTimer")) else None

    @property
    def native_min_value(self):
        return self.state_data.limits(self.definition).get("min", 0)

    @property
    def native_max_value(self):
        return self.state_data.limits(self.definition).get("max", 65535)

    @property
    def native_step(self):
        return self.state_data.limits(self.definition).get("step", 1) or 1

    @property
    def native_value(self):
        return self.state_data.decode(self.definition)

    async def async_set_native_value(self, value):
        if value != int(value):
            raise user_error('whole_number_required')
        await self.write(int(value))


class QuickOff(Control, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "min"
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 30

    @property
    def native_value(self):
        s = self.state_data
        hour = s.decode(self.definition)
        minute = s.decode(s.find_suffix(".Setting.QuickOffTime.Minute", "settings"))
        if hour == 31 and minute == 63:
            return 0
        return hour * 60 + minute if isinstance(hour, int) and isinstance(minute, int) and hour < 24 and minute < 60 else None

    async def async_set_native_value(self, value):
        if value != int(value) or value < 0 or value > 300 or value % 30:
            raise user_error('quick_off_range')
        s = self.state_data
        if value == 0:
            d = s.find_suffix(".Command.QuickOff.Cancel", "commands")
            await self.coordinator.apply(self.uuid, command=d["key"])
        else:
            minute = s.find_suffix(".Setting.QuickOffTime.Minute", "settings")
            await self.coordinator.apply(self.uuid, updates=[(self.key, int(value) // 60), (minute["key"], int(value) % 60)])
