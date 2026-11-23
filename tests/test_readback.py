"""Readback checks target fields while preserving strict command confirmation."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from test_coordinator import Cloud, HAError
from custom_components.vestel_appliances.coordinator import Coordinator
from custom_components.vestel_appliances.fields import Field
from custom_components.vestel_appliances.protocol import Device


class ReadbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture = Path(__file__).parent / "fixtures/device-snapshot.json"
        self.fixtures = json.loads(fixture.read_text())["devices"]
        self.use_device("RF")

    def use_device(self, family):
        fixture = next(d for d in self.fixtures if d["metadata"]["deviceType"] == family)
        metadata = {**fixture["metadata"], "deviceId": "test-device"}
        self.cloud = Cloud(metadata, fixture["registers"])
        self.state = Device(metadata, fixture["discovery"], dict(fixture["registers"]))
        self.coordinator = Coordinator(None, SimpleNamespace(data={"home_id": "test-home"}), self.cloud)
        self.coordinator.data = {"test-device": self.state}
        self.coordinator.schemas = {"test-device": self.state.discovery}

    def field(self, suffix):
        return self.state.find_suffix(suffix, "settings", "options", "commands")

    def set_field(self, suffix, value):
        code = Field(self.field(suffix)).replace_bits(self.cloud.registers, value)
        self.cloud.registers[code[:7]] = code[7:]

    def change_after_send(self, change):
        original = self.cloud.send

        async def send(device, code):
            await original(device, code)
            change()

        self.cloud.send = send

    async def apply(self, updates=None, command=None):
        with patch("custom_components.vestel_appliances.coordinator.asyncio.sleep", new=AsyncMock()):
            return await self.coordinator.apply("test-device", updates=updates, command=command)

    async def test_cooler_write_confirms_when_freezer_changes(self):
        self.change_after_send(lambda: self.set_field(".Freezer.Temperature", 20))
        result = await self.apply([(self.field(".Cooler.Temperature")["key"], 5)])
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.cloud.sent, ["RFTEMSE01298"])
        self.assertEqual(Field(self.field(".Freezer.Temperature")).raw(self.cloud.registers), 20)

    async def test_unrelated_change_cannot_confirm_wrong_target(self):
        def change():
            self.set_field(".Cooler.Temperature", 4)
            self.set_field(".Freezer.Temperature", 20)

        self.change_after_send(change)
        with self.assertRaises(HAError):
            await self.apply([(self.field(".Cooler.Temperature")["key"], 5)])
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.assertEqual(len(self.cloud.sent), 1)

    async def test_late_poll_confirms_target_despite_unrelated_change(self):
        self.cloud.echo = False
        with self.assertRaises(HAError):
            await self.apply([(self.field(".Cooler.Temperature")["key"], 5)])
        self.set_field(".Cooler.Temperature", 5)
        self.set_field(".Freezer.Temperature", 20)
        await self.coordinator._async_update_data()
        self.assertTrue(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.assertNotIn("test-device", self.coordinator.pending)
        self.assertEqual(len(self.cloud.sent), 1)

    def test_all_requested_fields_in_shared_register_must_match(self):
        updates = [(self.field(".Cooler.Temperature")["key"], 5),
                   (self.field(".Freezer.Temperature")["key"], 20)]
        codes = self.state.build(updates)
        expected = self.state.expected_readback(codes, updates=updates)
        for suffix, value in ((".Cooler.Temperature", 4), (".Freezer.Temperature", 18)):
            with self.subTest(suffix=suffix):
                self.cloud.registers["RFTEMSE"] = codes[0][7:]
                self.set_field(suffix, value)
                self.assertFalse(expected.matches(self.cloud.registers))
        self.cloud.registers["RFTEMSE"] = str(int(codes[0][7:]) | (1 << 15))
        self.assertTrue(expected.matches(self.cloud.registers))

    async def test_all_requested_registers_must_match(self):
        updates = [(self.field(".Cooler.Temperature")["key"], 5),
                   (self.field(".Setting.ScreenSaver")["key"], 0)]
        self.change_after_send(lambda: self.set_field(".Cooler.Temperature", 4))
        with self.assertRaises(HAError):
            await self.apply(updates)
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.assertEqual(len(self.cloud.sent), 2)

    async def test_field_without_bit_layout_still_requires_full_match(self):
        self.change_after_send(lambda: self.cloud.registers.update(RFMODEA="00006"))
        with self.assertRaises(HAError):
            await self.apply([(self.field(".Setting.Mode")["key"], 2)])
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])

    async def test_timer_cancel_confirms_despite_temperature_change(self):
        self.use_device("AC")
        self.change_after_send(lambda: self.cloud.registers.update(ACTEMOT="32760"))
        result = await self.apply(command=self.field(".Command.AutoOn.Cancel")["key"])
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.cloud.sent, ["ACTEMOT32759"])

    async def test_incompatible_toggles_must_also_be_cleared(self):
        self.use_device("AC")
        self.cloud.registers.update(ACGENSI="00001", ACFANPO=str(512 | 128))
        self.change_after_send(lambda: self.cloud.registers.update(
            ACFANPO=str(int(self.cloud.registers["ACFANPO"]) | 512)))
        with self.assertRaises(HAError):
            await self.apply([(self.field(".Fan.Turbo")["key"], 1)])
        self.assertFalse(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.cloud.registers["ACFANPO"] = "00001"
        await self.coordinator._async_update_data()
        self.assertTrue(self.coordinator.last_commands["test-device"]["readback_confirmed"])
        self.assertEqual(len(self.cloud.sent), 1)

    def test_invalid_or_missing_registers_cannot_confirm(self):
        updates = [(self.field(".Cooler.Temperature")["key"], 5)]
        expected = self.state.expected_readback(self.state.build(updates), updates=updates)
        for value in (None, True, 1298.0, [], {}, "invalid", "01298.0", -1, 65536, "１２９８"):
            with self.subTest(value=value):
                self.assertFalse(expected.matches({"RFTEMSE": value}))
        self.assertFalse(expected.matches({}))
        self.assertFalse(expected.matches(None))
