"""Malformed nested cloud responses produce safe API errors."""
import unittest
from unittest.mock import AsyncMock

import test_coordinator  # noqa: F401 -- initialize the shared minimal HA runtime
from custom_components.vestel_appliances.api import Api, ApiError


class ResponseValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_device_containers_raise_api_error(self):
        api = Api(None, {})
        for items in (None, [], ["unexpected"], "unexpected", 42, True):
            with self.subTest(items=items):
                api.request = AsyncMock(return_value={"items": items})
                with self.assertRaises(ApiError):
                    await api.devices("test-home")

    async def test_invalid_device_lists_raise_api_error(self):
        api = Api(None, {})
        for devices in (None, {}, "unexpected", 42):
            with self.subTest(devices=devices):
                api.request = AsyncMock(return_value={"items": {"homeappliances": devices}})
                with self.assertRaises(ApiError):
                    await api.devices("test-home")

    async def test_valid_device_lists_are_preserved(self):
        api = Api(None, {})
        for devices in ([], [{"deviceId": "test-device"}]):
            with self.subTest(devices=devices):
                api.request = AsyncMock(return_value={"items": {"homeappliances": devices}})
                self.assertIs(await api.devices("test-home"), devices)

    async def test_invalid_billing_device_records_raise_api_error(self):
        api = Api(None, {})
        for device in (None, [], "unexpected", 42):
            with self.subTest(device=device):
                api.request = AsyncMock(return_value={"data": {"home": {}, "devices": [device]}})
                with self.assertRaises(ApiError):
                    await api.billing_settings("test-home")

    async def test_valid_billing_response_is_preserved(self):
        api = Api(None, {})
        settings = {"home": {}, "devices": [{"deviceId": "test-device"}]}
        api.request = AsyncMock(return_value={"data": settings})
        self.assertIs(await api.billing_settings("test-home"), settings)
