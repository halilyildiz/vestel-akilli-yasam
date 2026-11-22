"""Authenticate directly and select an existing Vestel home."""
from __future__ import annotations
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Api, ApiError, AuthError
from .const import APP_NAME, DOMAIN


class Flow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._login_api: Api | None = None
        self._homes: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            api = Api(async_get_clientsession(self.hass), {
                "email": user_input["email"].strip(), "password": user_input["password"],
            })
            try:
                homes = await api.homes()
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                if not homes:
                    return self.async_abort(reason="no_homes")
                self._login_api = api
                self._homes = homes
                return await self.async_step_home()
        return self.async_show_form(step_id="user", errors=errors,
            data_schema=vol.Schema({vol.Required("email"): str,
                                   vol.Required("password"): str}))

    async def async_step_home(self, user_input: dict[str, str] | None = None):
        if self._login_api is None:
            return await self.async_step_user()
        errors: dict[str, str] = {}
        if user_input is not None:
            home_id = user_input.get("home_id")
            if home_id not in self._homes:
                errors["base"] = "invalid_home"
            else:
                await self.async_set_unique_id(home_id)
                self._abort_if_unique_id_configured()
                try:
                    await self._login_api.devices(home_id)
                except AuthError:
                    self._login_api = None
                    self._homes = {}
                    return await self.async_step_user()
                except ApiError:
                    errors["base"] = "cannot_connect"
                else:
                    data = {**self._login_api.credentials, "home_id": home_id}
                    self._login_api = None
                    self._homes = {}
                    return self.async_create_entry(title=APP_NAME, data=data)
        return self.async_show_form(step_id="home", errors=errors,
            data_schema=vol.Schema({vol.Required("home_id"): vol.In(self._homes)}))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            data.pop("refresh_token", None)
            api = Api(async_get_clientsession(self.hass), data)
            try:
                await api.devices(data["home_id"])
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                data["refresh_token"] = api.credentials.get("refresh_token", "")
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(step_id="reauth_confirm", errors=errors,
            data_schema=vol.Schema({vol.Required("email", default=entry.data.get("email", "")): str,
                                   vol.Required("password"): str}))
