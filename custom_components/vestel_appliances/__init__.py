from __future__ import annotations
import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import SupportsResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .errors import user_error
from .api import Api, ApiError
from .const import APP_NAME, DOMAIN
from .coordinator import Coordinator
from .energy import EnergyCoordinator
from .live import LiveUpdates

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SWITCH, Platform.NUMBER,
             Platform.BUTTON, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.TIME]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    def resolve(device_id):
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise user_error('device_not_found')
        uuid = next((identifier for domain, identifier in device.identifiers if domain == DOMAIN), None)
        coordinator = next((c for c in hass.data.get(DOMAIN, {}).values() if uuid in (c.data or {})), None)
        if coordinator is None:
            raise user_error('vestel_device_not_found')
        return uuid, coordinator

    async def get_consumption(call):
        uuid, coordinator = resolve(call.data["device_id"])
        try:
            return await coordinator.api.consumption(coordinator.entry.data["home_id"], uuid,
                call.data["period"], call.data["count"])
        except ApiError as err:
            raise user_error(err) from None

    async def billing(call):
        uuid, coordinator = resolve(call.data["device_id"])
        home = coordinator.entry.data["home_id"]
        try:
            if call.service == "get_billing_settings":
                return coordinator.api.billing_view(await coordinator.api.billing_settings(home), uuid)
            if call.service == "set_bill_limit":
                if call.data["scope"] == "home":
                    result = await coordinator.api.set_home_bill_limit(home, call.data["amount"], call.data["enabled"])
                else:
                    result = await coordinator.api.set_bill_limit(home, uuid, call.data["amount"], call.data["enabled"])
            elif call.service == "set_energy_price":
                result = await coordinator.api.set_energy_price(home, call.data["price"], call.data["currency"])
            elif call.service == "set_subscriber_type":
                result = await coordinator.api.set_billing_option(home, "subscriber_type", call.data["subscriber_type"])
            elif call.service == "set_tariff_type":
                result = await coordinator.api.set_billing_option(home, "tariff_type", call.data["tariff_type"])
            elif call.service == "set_energy_management":
                result = await coordinator.api.set_billing_option(home, "energy_management", "enable" if call.data["enabled"] else "disable")
            else:
                raise user_error('billing_action_unsupported')
            # A new reading updates sensors, never invents a successful write.
            await coordinator.energy.async_refresh_billing()
            if not result["readback_confirmed"]:
                raise user_error('billing_unconfirmed')
            return result
        except ApiError as err:
            raise user_error(err) from None

    async def apply(call):
        device = dr.async_get(hass).async_get(call.data["device_id"])
        if device is None:
            raise user_error('device_not_found')
        uuid = next((identifier for domain, identifier in device.identifiers if domain == DOMAIN), None)
        coordinator = next((c for c in hass.data.get(DOMAIN, {}).values() if uuid in (c.data or {})), None)
        if coordinator is None:
            raise user_error('vestel_device_not_found')
        if call.data.get("command"):
            if call.data.get("updates"):
                raise user_error('separate_changes')
            return await coordinator.apply(uuid, command=call.data["command"])
        updates = call.data.get("updates") or []
        if not updates:
            raise user_error('choose_change')
        return await coordinator.apply(uuid, updates=[(v["key"], v["value"]) for v in updates])

    hass.services.async_register(DOMAIN, "apply", apply, supports_response=SupportsResponse.OPTIONAL,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Optional("command"): cv.string,
            vol.Optional("updates"): [{vol.Required("key"): cv.string, vol.Required("value"): int}]}))
    hass.services.async_register(DOMAIN, "get_consumption", get_consumption,
        supports_response=SupportsResponse.ONLY,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Optional("period", default="month"): vol.In(["day", "week", "month"]),
            vol.Optional("count", default=12): vol.All(vol.Coerce(int), vol.Range(min=1, max=366))}))
    hass.services.async_register(DOMAIN, "get_billing_settings", billing,
        supports_response=SupportsResponse.ONLY,
        schema=vol.Schema({vol.Required("device_id"): cv.string}))
    hass.services.async_register(DOMAIN, "set_bill_limit", billing,
        supports_response=SupportsResponse.OPTIONAL,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Optional("scope", default="device"): vol.In(["device", "home"]),
            vol.Required("amount"): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required("enabled"): cv.boolean}))
    hass.services.async_register(DOMAIN, "set_energy_price", billing,
        supports_response=SupportsResponse.OPTIONAL,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Required("price"): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required("currency"): cv.string}))
    hass.services.async_register(DOMAIN, "set_subscriber_type", billing,
        supports_response=SupportsResponse.OPTIONAL,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Required("subscriber_type"): vol.In(["residential", "business", "industrial"])}))
    hass.services.async_register(DOMAIN, "set_tariff_type", billing,
        supports_response=SupportsResponse.OPTIONAL,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Required("tariff_type"): vol.In(["one-time", "three-time"])}))
    hass.services.async_register(DOMAIN, "set_energy_management", billing,
        supports_response=SupportsResponse.OPTIONAL,
        schema=vol.Schema({vol.Required("device_id"): cv.string,
            vol.Required("enabled"): cv.boolean}))
    return True


async def async_setup_entry(hass, entry):
    if entry.title in {"Vestel Cihazları", "Akıllı Yaşam", "Vestel Akıllı Yaşam"}:
        hass.config_entries.async_update_entry(entry, title=APP_NAME)
    def update_token(token):
        hass.config_entries.async_update_entry(entry, data={**entry.data, "refresh_token": token})
    api = Api(async_get_clientsession(hass), entry.data, update_token)
    coordinator = Coordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    coordinator.energy = EnergyCoordinator(hass, entry, coordinator)
    coordinator.live = LiveUpdates(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.live.start()
    # Optional history must not delay controls or live status subscriptions.
    coordinator.energy.start(hass)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].energy.stop()
        await hass.data[DOMAIN][entry.entry_id].live.stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
