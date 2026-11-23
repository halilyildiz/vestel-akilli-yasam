"""Direct login and home selection, using a fake cloud; no credentials/network."""
from __future__ import annotations
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import test_coordinator  # noqa: F401 -- initialize the shared minimal HA test runtime
from custom_components.vestel_appliances.api import Api, ApiError, AuthError


class ConfigFlow:
    def __init_subclass__(cls, **kwargs): pass
    def async_show_form(self, **kwargs): return {"type": "form", **kwargs}
    def async_abort(self, **kwargs): return {"type": "abort", **kwargs}
    def async_create_entry(self, **kwargs): return {"type": "create_entry", **kwargs}
    async def async_set_unique_id(self, value): self.unique_id = value
    def _abort_if_unique_id_configured(self): pass


def load_flow():
    config = types.ModuleType("homeassistant.config_entries")
    config.ConfigFlow = ConfigFlow
    http = types.ModuleType("homeassistant.helpers.aiohttp_client")
    http.async_get_clientsession = lambda hass: None
    vol = types.ModuleType("voluptuous")
    vol.Required = lambda key, **kw: key
    vol.Schema = lambda value: value
    vol.In = lambda value: tuple(value)
    name = "custom_components.vestel_appliances._test_config_flow"
    path = Path(__file__).resolve().parents[1] / "custom_components/vestel_appliances/config_flow.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"homeassistant.config_entries": config,
                                 "homeassistant.helpers.aiohttp_client": http,
                                 "voluptuous": vol}):
        spec.loader.exec_module(module)
    return module


class LoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = load_flow()
        self.flow = self.module.Flow()
        self.flow.hass = object()
        self.api = Api(None, {"email": "example@example.com", "password": "test-only", "refresh_token": "test-token"})
        self.api.homes = AsyncMock(return_value={"home-a": "Ev"})
        self.api.devices = AsyncMock(return_value=[])
        self.mock = patch.object(self.module, "Api", return_value=self.api)
        self.constructor = self.mock.start()
        self.addCleanup(self.mock.stop)

    async def login(self):
        return await self.flow.async_step_user({"email": " example@example.com ", "password": "test-only"})

    async def test_login_selects_only_authorized_home_and_preserves_refresh_token(self):
        result = await self.login()
        self.assertEqual(result["step_id"], "home")
        self.assertEqual(self.constructor.call_args.args[1]["email"], "example@example.com")
        invalid = await self.flow.async_step_home({"home_id": "foreign-home"})
        self.assertEqual(invalid["errors"]["base"], "invalid_home")
        self.api.devices.assert_not_called()
        result = await self.flow.async_step_home({"home_id": "home-a"})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Vestel Smart Life")
        self.assertEqual(result["data"]["home_id"], "home-a")
        self.assertEqual(result["data"]["refresh_token"], "test-token")
        self.assertIsNone(self.flow._login_api)
        self.api.devices.assert_awaited_once_with("home-a")

    async def test_invalid_credentials(self):
        self.api.homes.side_effect = AuthError("denied")
        self.assertEqual((await self.login())["errors"]["base"], "invalid_auth")

    async def test_network_error(self):
        self.api.homes.side_effect = ApiError("offline")
        self.assertEqual((await self.login())["errors"]["base"], "cannot_connect")

    async def test_no_homes(self):
        self.api.homes.return_value = {}
        self.assertEqual((await self.login())["reason"], "no_homes")

    async def test_homes_response_validation(self):
        api = Api(None, {})
        api.request = AsyncMock(return_value={"items": [{"homeId": "home-a", "homeName": "Ev"}]})
        self.assertEqual(await api.homes(), {"home-a": "Ev"})
        api.request.assert_awaited_once_with("GET", "/homes")
        for body in ({}, {"items": {}}, {"items": [None]}, {"items": [{"homeId": ""}]}):
            api.request.return_value = body
            with self.assertRaises(ApiError): await api.homes()
