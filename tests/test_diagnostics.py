"""Diagnostics expose technical context while removing private cloud data."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import test_coordinator  # noqa: F401 -- shared minimal HA runtime
from custom_components.vestel_appliances.diagnostics import async_get_config_entry_diagnostics
from custom_components.vestel_appliances.protocol import Device
from custom_components.vestel_appliances.redaction import (
    _private_values, collect, metadata_view, sanitize,
)


class RedactionTests(unittest.TestCase):
    def test_nested_fields_lists_and_serialized_json_are_redacted(self):
        value = {"nested": [{"E-mail": "private@example.invalid", "refresh_token": "private-refresh"}],
                 "encoded": json.dumps({"items": [{"password": "private-password"}]}),
                 "cookies": {"session": "private-cookie"}, "AccessKeyId": "private-access-key"}
        original = copy.deepcopy(value)
        result = sanitize(value)
        serialized = json.dumps(result)
        for secret in ("private@example.invalid", "private-refresh", "private-password",
                       "private-cookie", "private-access-key"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(json.loads(result["encoded"])["items"][0]["password"], "[REDACTED]")
        self.assertEqual(value, original)

    def test_nested_private_values_are_removed_when_repeated_in_plain_text(self):
        metadata = {"nested": [{"serialNumber": "test-serial-123"}],
                    "encoded": json.dumps({"refreshToken": "test-refresh-456"})}
        private = _private_values([metadata], "test-home")
        result = sanitize({"note": "test-serial-123 / test-refresh-456 / test-home"}, private)
        self.assertEqual(result["note"], "[REDACTED] / [REDACTED] / [REDACTED]")

    def test_identifiers_in_keys_and_text_are_removed(self):
        uuid = "12345678-1234-1234-1234-123456789abc"
        result = sanitize({uuid: "private@example.invalid aa:bb:cc:dd:ee:ff"})
        serialized = json.dumps(result)
        for identifier in (uuid, "private@example.invalid", "aa:bb:cc:dd:ee:ff"):
            self.assertNotIn(identifier, serialized)

    def test_metadata_only_exports_known_scalar_fields(self):
        metadata = {"deviceType": "AC", "deviceModel": "EXAMPLE", "connected": True,
                    "wifiVersion": {"futureField": "private-value"},
                    "ownerAlias": "private-owner", "futureCloudField": "private-new-field"}
        self.assertEqual(metadata_view(metadata), {
            "deviceType": "AC", "deviceModel": "EXAMPLE", "connected": True})


class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.uuid = "synthetic-device-id"
        metadata = {
            "deviceId": self.uuid, "deviceType": "AC", "deviceModel": "EXAMPLE-AC",
            "wifiVersion": "1.2.3", "connected": True,
            "deviceName": "private-device-name", "ownerAlias": "private-owner",
            "futureCloudField": "private-future-field",
            "nested": {"serialNumber": "private-serial"},
        }
        self.state = Device(metadata, {
            "deviceType": "AC", "settings": [{"key": "Setting.Temperature", "valueType": "Integer"}],
            "nested": [{"email": "private@example.invalid", "token": "private-cloud-token"}],
            "note": "private-serial / private-password / private-refresh / private-cloud-token",
            "encoded": json.dumps({"deviceId": self.uuid, "password": "private-password"}),
        }, {"ACTEMOT": "00008"})
        self.coordinator = SimpleNamespace(
            api=SimpleNamespace(inventory_summary={"homeappliances": 1}),
            data={self.uuid: self.state}, unsupported_types={"OV": 1},
            compatibility_errors={self.uuid: "SchemaError"},
            platform_errors={("climate", self.uuid)},
            live=SimpleNamespace(stats={"state": "connected", "messages_received": 3}),
            last_commands={self.uuid: {"accepted": True, "readback_confirmed": False}})
        self.entry = SimpleNamespace(entry_id="test-entry", data={
            "home_id": "private-home", "email": "private@example.invalid",
            "password": "private-password", "refresh_token": "private-refresh"})
        self.hass = SimpleNamespace(data={"vestel_appliances": {self.entry.entry_id: self.coordinator}})

    async def test_export_omits_unknown_metadata_and_redacts_nested_secrets(self):
        before_state, before_entry = copy.deepcopy(self.state), copy.deepcopy(self.entry.data)
        result = await async_get_config_entry_diagnostics(self.hass, self.entry)
        serialized = json.dumps(result)
        for secret in (self.uuid, "private-home", "private@example.invalid", "private-password",
                       "private-refresh", "private-cloud-token", "private-serial", "private-device-name",
                       "private-owner", "private-future-field"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(result["devices"][0]["metadata"], {
            "deviceType": "AC", "deviceModel": "EXAMPLE-AC", "wifiVersion": "1.2.3", "connected": True})
        self.assertEqual(self.state, before_state)
        self.assertEqual(self.entry.data, before_entry)

    async def test_technical_definitions_status_and_command_results_remain_useful(self):
        result = await async_get_config_entry_diagnostics(self.hass, self.entry)
        device = result["devices"][0]
        self.assertEqual(device["discovery"]["settings"], self.state.discovery["settings"])
        self.assertEqual(device["registers"], {"ACTEMOT": "00008"})
        self.assertTrue(device["read_ok"])
        self.assertEqual(device["last_command"], {"accepted": True, "readback_confirmed": False})
        self.assertEqual(result["compatibility"]["unsupported_types"], {"OV": 1})
        self.assertEqual(result["live_updates"]["messages_received"], 3)

    async def test_device_id_is_redacted_even_when_missing_from_metadata(self):
        self.state.metadata.pop("deviceId")
        result = await async_get_config_entry_diagnostics(self.hass, self.entry)
        self.assertNotIn(self.uuid, json.dumps(result))

    async def test_empty_account_still_produces_diagnostics(self):
        self.coordinator.data = {}
        self.coordinator.compatibility_errors = {}
        self.coordinator.platform_errors = set()
        result = await async_get_config_entry_diagnostics(self.hass, self.entry)
        self.assertEqual(result["devices"], [])

    async def test_read_only_collector_uses_same_metadata_filter(self):
        api = SimpleNamespace(
            async_get_devices=AsyncMock(return_value=[self.state.metadata]),
            async_get_discovery=AsyncMock(return_value={"deviceType": "AC"}),
            async_get_status=AsyncMock(return_value=self.state.registers))
        result = await collect(api, "private-home")
        metadata = result["devices"][0]["metadata"]
        self.assertEqual(metadata["deviceModel"], "EXAMPLE-AC")
        self.assertNotIn("ownerAlias", metadata)
        self.assertNotIn("deviceId", metadata)
