from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from .dynamic import setup_dynamic_entities
from .entity import Base

MODES = {"Auto": HVACMode.AUTO, "Cooling": HVACMode.COOL, "Heating": HVACMode.HEAT,
         "Dehumidifying": HVACMode.DRY, "Ventilating": HVACMode.FAN_ONLY, "PowerOff": HVACMode.OFF}
NATIVE = hasattr(ClimateEntity, "native_current_temperature")


async def async_setup_entry(hass, entry, add):
    setup_dynamic_entities(hass, entry, add, _entities)


def _entities(c, uuid, state):
    if state.family != "AC":
        return []
    if not state.find_suffix(".Setting.Mode", "settings") or not state.find_suffix(".Setting.Temperature", "settings"):
        raise ValueError("Climate description lacks mode or temperature")
    return [Climate(c, uuid, {"key": "climate"})]


class Climate(Base, ClimateEntity):
    _attr_target_temperature_step = 1
    _attr_supported_features = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
                               | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF)
    if NATIVE:
        _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    else:
        _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, *args):
        super().__init__(*args)
        self._attr_name = None
        if self.field(".Fan.Speed") is None:
            self._attr_supported_features = self._attr_supported_features & ~ClimateEntityFeature.FAN_MODE

    def field(self, suffix):
        return self.state_data.find_suffix(suffix, "settings")

    @property
    def hvac_modes(self):
        return [MODES[v["value"].rsplit(".", 1)[-1]] for v in (self.field(".Setting.Mode") or {}).get("values", [])
                if v["value"].rsplit(".", 1)[-1] in MODES]

    @property
    def hvac_mode(self):
        name = self.state_data.decode(self.field(".Setting.Mode"))
        return MODES.get(str(name).rsplit(".", 1)[-1])

    @property
    def native_current_temperature(self):
        return self.state_data.status(".RoomTemperature")

    @property
    def native_target_temperature(self):
        return self.state_data.decode(self.field(".Setting.Temperature"))

    if not NATIVE:
        current_temperature = native_current_temperature
        target_temperature = native_target_temperature

    @property
    def min_temp(self):
        return self.state_data.limits(self.field(".Setting.Temperature")).get("min", 16)

    @property
    def max_temp(self):
        return self.state_data.limits(self.field(".Setting.Temperature")).get("max", 30)

    @property
    def fan_modes(self):
        return [v["value"].rsplit(".", 1)[-1] for v in self.state_data.values(self.field(".Fan.Speed"))] if self.field(".Fan.Speed") else []

    @property
    def fan_mode(self):
        value = self.state_data.decode(self.field(".Fan.Speed"))
        return value.rsplit(".", 1)[-1] if value else None

    async def async_set_hvac_mode(self, hvac_mode):
        d = self.field(".Setting.Mode")
        value = next((v["commandValue"] for v in d["values"] if MODES.get(v["value"].rsplit(".", 1)[-1]) == hvac_mode), None)
        if value is None:
            raise HomeAssistantError("Desteklenmeyen klima modu.")
        await self.coordinator.apply(self.uuid, updates=[(d["key"], value)])

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self):
        previous = str(self.state_data.status(".CurrentMode") or "").rsplit(".", 1)[-1]
        await self.async_set_hvac_mode(MODES.get(previous, HVACMode.COOL))

    async def async_set_temperature(self, **kwargs):
        value = kwargs.get(ATTR_TEMPERATURE)
        if value is None or value != int(value):
            raise HomeAssistantError("Tam derece girin.")
        await self.coordinator.apply(self.uuid, updates=[(self.field(".Setting.Temperature")["key"], int(value))])

    async def async_set_fan_mode(self, fan_mode):
        d = self.field(".Fan.Speed")
        value = next((v["commandValue"] for v in self.state_data.values(d) if v["value"].endswith("." + fan_mode)), None)
        if value is None:
            raise HomeAssistantError("Bu modda fan hızı kullanılamıyor.")
        await self.coordinator.apply(self.uuid, updates=[(d["key"], value)])
