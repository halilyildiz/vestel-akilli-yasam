"""Exercise write sequencing against a fake cloud, with minimal HA stubs."""
import copy
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components/vestel_appliances"
for name, path in (("custom_components", ROOT / "custom_components"), ("custom_components.vestel_appliances", PKG)):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module

for name in ("homeassistant", "homeassistant.exceptions", "homeassistant.helpers", "homeassistant.helpers.update_coordinator", "aiohttp"):
    sys.modules.setdefault(name, types.ModuleType(name))

class HAError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.translation_domain = kwargs.get("translation_domain")
        self.translation_key = kwargs.get("translation_key")
        self.translation_placeholders = kwargs.get("translation_placeholders")
class HAAuthError(HAError): pass
class UpdateError(HAError): pass
sys.modules["homeassistant.exceptions"].HomeAssistantError = HAError
sys.modules["homeassistant.exceptions"].ConfigEntryAuthFailed = HAAuthError

class DataCoordinator:
    def __init__(self, *args, **kwargs): self.data = {}
    def async_set_updated_data(self, data): self.data = data
sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = DataCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = UpdateError
sys.modules["aiohttp"].ClientError = type("ClientError", (Exception,), {})

from custom_components.vestel_appliances.coordinator import Coordinator
from custom_components.vestel_appliances.protocol import Device
from custom_components.vestel_appliances.api import ApiError, AuthError


class Cloud:
    def __init__(self, metadata, registers):
        self.metadata = copy.deepcopy(metadata)
        self.registers = dict(registers)
        self.sent = []
        self.echo = True
        self.empty = False
        self.status_reads = 0

    async def devices(self, home): return [self.metadata]
    async def status(self, uuid):
        self.status_reads += 1
        return {} if self.empty else dict(self.registers)
    async def send(self, device, code):
        self.sent.append(code)
        if self.echo: self.registers[code[:7]] = code[7:]


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = json.loads((ROOT / "tests/fixtures/device-snapshot.json").read_text())
        rf = next(d for d in fixture["devices"] if d["metadata"]["deviceType"] == "RF")
        self.meta = {**rf["metadata"], "deviceId": "test-device"}
        self.cloud = Cloud(self.meta, rf["registers"])
        self.coordinator = Coordinator(None, types.SimpleNamespace(data={"home_id": "test-home"}), self.cloud)
        self.coordinator.data = {"test-device": Device(self.meta, rf["discovery"], dict(rf["registers"]))}
        self.coordinator.schemas = {"test-device": rf["discovery"]}
        self.key = "Refrigeration.Refrigerator.Setting.ScreenSaver"

    async def apply(self):
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            return await self.coordinator.apply("test-device", updates=[(self.key, 0)])

    async def test_readback_confirms_one_write(self):
        result = await self.apply()
        self.assertEqual(self.cloud.sent, ["RFSSAVE00000"])
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.cloud.status_reads, 2)

    async def test_missing_echo_does_not_resend_or_fabricate_state(self):
        self.cloud.echo = False
        with self.assertRaises(HAError): await self.apply()
        self.assertEqual(self.cloud.sent, ["RFSSAVE00000"])
        self.assertEqual(self.cloud.status_reads, 7)
        self.assertEqual(self.coordinator.data["test-device"].registers["RFSSAVE"], "00001")
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])

    async def test_empty_fresh_status_blocks_all_writes(self):
        self.cloud.empty = True
        with self.assertRaises(HAError): await self.apply()
        self.assertEqual(self.cloud.sent, [])

    async def test_fresh_offline_metadata_blocks_all_writes(self):
        self.cloud.metadata["connected"] = False
        with self.assertRaises(HAError): await self.apply()
        self.assertEqual(self.cloud.sent, [])

    async def test_whole_register_merge_uses_fresh_cloud_value(self):
        self.cloud.registers["RFTEMSE"] = "01044"  # Freezer changed since the poll.
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            await self.coordinator.apply("test-device", updates=[("Refrigeration.Refrigerator.Setting.Cooler.Temperature", 5)])
        self.assertEqual(self.cloud.sent, ["RFTEMSE01300"])

    async def test_offline_device_keeps_metadata_without_stale_state(self):
        self.cloud.metadata["connected"] = False
        result = await self.coordinator._async_update_data()
        self.assertIn("test-device", result)
        self.assertFalse(result["test-device"].read_ok)
        self.assertEqual(result["test-device"].registers, {})

    async def test_delayed_readback_is_confirmed_without_resending(self):
        self.cloud.echo = False
        original = self.cloud.status
        async def delayed(uuid):
            if self.cloud.status_reads >= 4: self.cloud.registers["RFSSAVE"] = "00000"
            return await original(uuid)
        self.cloud.status = delayed
        result = await self.apply()
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.cloud.sent, ["RFSSAVE00000"])

    async def test_dw_cancel_reports_drain_in_progress(self):
        fixture = json.loads((ROOT / "tests/fixtures/device-snapshot.json").read_text())
        dw = next(d for d in fixture["devices"] if d["metadata"]["deviceType"] == "DW")
        self.cloud.metadata = {**dw["metadata"], "deviceId": "test-device"}
        self.cloud.registers = dict(dw["registers"])
        self.coordinator.data["test-device"] = Device(self.cloud.metadata, dw["discovery"], self.cloud.registers)
        self.coordinator.schemas["test-device"] = dw["discovery"]
        async def cancel(device, code):
            self.cloud.sent.append(code)
            self.cloud.registers["DWWARNS"] = "00001"
        self.cloud.send = cancel
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            result = await self.coordinator.apply("test-device", command="Dishcare.DishWasher.Command.Cancel")
        self.assertEqual(result["operation"], "cancelling")
        self.assertFalse(result["readback_confirmed"])
        self.assertEqual(self.cloud.sent, ["DWPROSI00000"])
        self.cloud.registers["DWPROSI"] = "00000"
        await self.coordinator._async_update_data()
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.cloud.registers["DWPROST"] = "00003"
        self.cloud.registers["DWWARNS"] = "00002"
        await self.coordinator._async_update_data()
        self.assertTrue(self.coordinator.last_commands["test-device"]["readback_confirmed"])

    async def test_running_cancel_is_not_sent_twice(self):
        fixture = json.loads((ROOT / "tests/fixtures/device-snapshot.json").read_text())
        dw = next(d for d in fixture["devices"] if d["metadata"]["deviceType"] == "DW")
        self.cloud.metadata = {**dw["metadata"], "deviceId": "test-device"}
        self.cloud.registers = {**dw["registers"], "DWWARNS": "00001"}
        self.coordinator.data["test-device"] = Device(self.cloud.metadata, dw["discovery"], self.cloud.registers)
        with self.assertRaises(HAError):
            await self.coordinator.apply("test-device", command="Dishcare.DishWasher.Command.Cancel")
        self.assertEqual(self.cloud.sent, [])


    def use_dw(self):
        fixture = json.loads((ROOT / "tests/fixtures/device-snapshot.json").read_text())
        dw = next(d for d in fixture["devices"] if d["metadata"]["deviceType"] == "DW")
        self.cloud.metadata = {**dw["metadata"], "deviceId": "test-device"}
        self.cloud.registers = {**dw["registers"], "DWPROST": "00000"}
        self.coordinator.data["test-device"] = Device(self.cloud.metadata, dw["discovery"], self.cloud.registers)
        self.coordinator.schemas["test-device"] = dw["discovery"]

    async def test_uv_confirms_result_state_instead_of_opcode(self):
        self.use_dw()
        async def send(device, code):
            self.cloud.sent.append(code)
            self.cloud.registers["DWSETTS"] = "00112"
        self.cloud.send = send
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            result = await self.coordinator.apply("test-device", command="Dishcare.DishWasher.Command.UvonOn")
        self.assertEqual(self.cloud.sent, ["DWSETTS00012"])
        self.assertTrue(result["readback_confirmed"])

    async def test_uv_opcode_echo_is_not_success_but_late_named_state_confirms(self):
        self.use_dw()
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(HAError):
                await self.coordinator.apply("test-device", command="Dishcare.DishWasher.Command.UvonOn")
        self.assertEqual(self.cloud.sent, ["DWSETTS00012"])
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.cloud.registers["DWSETTS"] = "00112"
        await self.coordinator._async_update_data()
        self.assertTrue(self.coordinator.last_commands["test-device"]["readback_confirmed"])

    async def test_cancel_reset_register_does_not_confirm_while_machine_is_running(self):
        self.use_dw()
        self.cloud.registers.update(DWPROST="00001", DWWARNS="00000")
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(HAError):
                await self.coordinator.apply("test-device", command="Dishcare.DishWasher.Command.Cancel")
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.cloud.registers["DWPROST"] = "00003"
        await self.coordinator._async_update_data()
        self.assertTrue(self.coordinator.last_commands["test-device"]["readback_confirmed"])

    async def test_listeners_observe_confirmed_metadata_immediately(self):
        observed = []
        original = self.coordinator.async_set_updated_data
        def publish(data):
            observed.append(copy.deepcopy(self.coordinator.last_commands["test-device"]))
            original(data)
        self.coordinator.async_set_updated_data = publish
        await self.apply()
        self.assertTrue(observed[-1]["readback_confirmed"])


if __name__ == "__main__": unittest.main()

class ConsumptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_endpoint_payload_and_privacy(self):
        from custom_components.vestel_appliances.api import Api
        api = Api(None, {})
        api.request = AsyncMock(return_value={
            "deviceId": "private-id", "deviceName": "private-name", "currencyShortCode": "TRY",
            "deviceConsumption": [{"date": "2026-11", "consumption": {
                "energyAmount": 3.25, "energyCost": 9.5, "water": None}}]})
        result = await api.consumption("home", "device", "month", 12)
        api.request.assert_awaited_once_with("POST",
            "/energymanagement/consumption/month?count=12&queryType=device",
            {"homeId": "home", "deviceId": "device"})
        self.assertEqual(result["samples"][0]["consumption"]["energyAmount"], 3.25)
        self.assertIsNone(result["samples"][0]["consumption"]["water"])
        self.assertTrue(result["estimated"])
        self.assertNotIn("private", json.dumps(result))

    async def test_missing_history_is_not_presented_as_zero(self):
        from custom_components.vestel_appliances.api import Api
        api = Api(None, {})
        api.request = AsyncMock(return_value={"message": "failure"})
        with self.assertRaises(ApiError): await api.consumption("h", "d")
        api.request = AsyncMock(return_value={"data": {"deviceConsumption": []}})
        self.assertEqual((await api.consumption("h", "d"))["samples"], [])

    async def test_invalid_query_never_sends_request(self):
        from custom_components.vestel_appliances.api import Api
        api = Api(None, {})
        api.request = AsyncMock()
        for period, count in (("delete", 12), ("month", 0), ("day", 367), ("day", True)):
            with self.subTest(period=period, count=count), self.assertRaises(ApiError):
                await api.consumption("h", "d", period, count)
        api.request.assert_not_awaited()
