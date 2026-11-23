"""Optional energy history must not block controls or survive entry unload."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_coordinator  # noqa: F401 -- shared minimal HA runtime
from custom_components.vestel_appliances.api import ApiError
from custom_components.vestel_appliances.energy import EnergyCoordinator


def load_setup():
    """Load the real entry setup functions with minimal import-time HA stubs."""
    const = types.ModuleType("homeassistant.const")
    const.Platform = types.SimpleNamespace(**{name: name.lower() for name in (
        "CLIMATE", "SELECT", "SWITCH", "NUMBER", "BUTTON", "SENSOR", "BINARY_SENSOR", "TIME")})
    core = types.ModuleType("homeassistant.core")
    core.SupportsResponse = types.SimpleNamespace(ONLY="only", OPTIONAL="optional")
    http = types.ModuleType("homeassistant.helpers.aiohttp_client")
    http.async_get_clientsession = lambda hass: None
    validation = types.ModuleType("homeassistant.helpers.config_validation")
    validation.config_entry_only_config_schema = lambda domain: {}
    modules = {
        "voluptuous": types.ModuleType("voluptuous"),
        "homeassistant.const": const, "homeassistant.core": core,
        "homeassistant.helpers.aiohttp_client": http,
        "homeassistant.helpers.config_validation": validation,
        "homeassistant.helpers.device_registry": types.ModuleType("homeassistant.helpers.device_registry"),
    }
    path = Path(__file__).parents[1] / "custom_components/vestel_appliances/__init__.py"
    spec = importlib.util.spec_from_file_location("custom_components.vestel_appliances._test_setup", path)
    spec.submodule_search_locations = None
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class StartupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_setup()
        self.tasks = []
        self.entry = types.SimpleNamespace(
            entry_id="test-entry", title="Vestel Smart Life", data={"home_id": "test-home"},
            async_create_background_task=self.create_task)
        self.hass = types.SimpleNamespace(data={}, config_entries=types.SimpleNamespace(
            async_forward_entry_setups=AsyncMock(), async_unload_platforms=AsyncMock(return_value=True)))
        self.api = types.SimpleNamespace(
            consumption=AsyncMock(return_value={"samples": []}),
            billing_settings=AsyncMock(return_value={"home": {}, "devices": []}))
        self.coordinator = types.SimpleNamespace(
            api=self.api, data={"one": None}, async_config_entry_first_refresh=AsyncMock())
        self.energy = EnergyCoordinator(self.hass, self.entry, self.coordinator)
        self.energy.data = None

        # Drive the real energy reader; only the base coordinator's publication
        # is substituted, since the offline runtime has no async_refresh method.
        async def refresh():
            self.energy.data = await self.energy._async_update_data()

        self.energy.async_refresh = refresh
        self.live = types.SimpleNamespace(start=Mock(), stop=AsyncMock())

    def create_task(self, hass, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self.tasks.append(task)
        return task

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def setup_entry(self):
        with (patch.object(self.module, "Api", return_value=self.api),
              patch.object(self.module, "Coordinator", return_value=self.coordinator),
              patch.object(self.module, "EnergyCoordinator", return_value=self.energy),
              patch.object(self.module, "LiveUpdates", return_value=self.live)):
            return await self.module.async_setup_entry(self.hass, self.entry)

    async def test_slow_energy_does_not_delay_controls_or_live_updates(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def consumption(*args):
            started.set()
            await release.wait()
            return {"samples": [{"consumption": {"energyAmount": 2}}]}

        self.api.consumption.side_effect = consumption
        self.assertTrue(await asyncio.wait_for(self.setup_entry(), timeout=1))
        await asyncio.wait_for(started.wait(), timeout=1)
        self.hass.config_entries.async_forward_entry_setups.assert_awaited_once()
        self.live.start.assert_called_once()
        self.assertIsNone(self.energy.data)
        self.assertFalse(self.energy._initial_refresh_task.done())
        release.set()
        await self.energy._initial_refresh_task
        self.assertEqual(self.energy.data["one"]["day"]["samples"][0]["consumption"]["energyAmount"], 2)

    async def test_platform_failure_does_not_start_background_work(self):
        self.hass.config_entries.async_forward_entry_setups.side_effect = RuntimeError("test setup failure")
        with self.assertRaises(RuntimeError):
            await self.setup_entry()
        self.assertEqual(self.tasks, [])
        self.live.start.assert_not_called()
        self.api.consumption.assert_not_awaited()

    async def test_energy_endpoint_failures_leave_setup_successful(self):
        self.api.consumption.side_effect = ApiError("test unavailable")
        self.api.billing_settings.side_effect = ApiError("test unavailable")
        self.assertTrue(await self.setup_entry())
        await self.energy._initial_refresh_task
        self.assertEqual(self.energy.data, {"one": {"day": None, "month": None}})
        self.live.start.assert_called_once()

    async def test_unload_cancels_pending_energy_requests(self):
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def consumption(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        self.api.consumption.side_effect = consumption
        await self.setup_entry()
        await asyncio.wait_for(started.wait(), timeout=1)
        task = self.energy._initial_refresh_task
        self.assertTrue(await self.module.async_unload_entry(self.hass, self.entry))
        self.assertTrue(task.cancelled())
        self.assertTrue(cancelled.is_set())
        self.assertIsNone(self.energy._initial_refresh_task)
        self.assertNotIn(self.entry.entry_id, self.hass.data["vestel_appliances"])
        self.live.stop.assert_awaited_once()

    async def test_failed_unload_keeps_background_work(self):
        await self.setup_entry()
        self.hass.config_entries.async_unload_platforms.return_value = False
        with patch.object(self.energy, "stop", new=AsyncMock()) as stop:
            self.assertFalse(await self.module.async_unload_entry(self.hass, self.entry))
        stop.assert_not_awaited()
        self.live.stop.assert_not_awaited()
        self.assertIn(self.entry.entry_id, self.hass.data["vestel_appliances"])

    async def test_start_is_idempotent_and_completed_fetch_unloads_cleanly(self):
        await self.setup_entry()
        first_task = self.energy._initial_refresh_task
        self.energy.start(self.hass)
        self.assertIs(self.energy._initial_refresh_task, first_task)
        self.assertEqual(len(self.tasks), 1)
        await first_task
        self.assertTrue(await self.module.async_unload_entry(self.hass, self.entry))
        await self.energy.stop()
        self.assertIsNone(self.energy._initial_refresh_task)

    async def test_legacy_default_title_is_updated(self):
        self.entry.title = "Vestel Akıllı Yaşam"
        self.hass.config_entries.async_update_entry = Mock()
        await self.setup_entry()
        self.hass.config_entries.async_update_entry.assert_called_once_with(
            self.entry, title="Vestel Smart Life")

    async def test_custom_entry_title_is_preserved(self):
        self.entry.title = "My kitchen appliances"
        self.hass.config_entries.async_update_entry = Mock()
        await self.setup_entry()
        self.hass.config_entries.async_update_entry.assert_not_called()
