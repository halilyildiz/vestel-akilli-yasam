"""Energy estimates must remain isolated from control and from missing data."""
import math
import types
import unittest
from unittest.mock import AsyncMock
# Reuse the minimal HA runtime stubs used by the command tests.
import test_coordinator
from custom_components.vestel_appliances.api import Api, ApiError
from custom_components.vestel_appliances.energy import EnergyCoordinator, sample_value

SETTINGS = {"home": {"homeId": "home-private", "kwhPrice": 3.238, "currencyShortCode": "TRY"},
            "devices": [{"deviceId": "device-private", "energyQuotaAmount": 50, "energyQuotaStatus": "disable"},
                        {"deviceId": "other-private", "energyQuotaAmount": 100, "energyQuotaStatus": "enable"}]}

class BillingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self): self.api = Api(None, {})

    async def test_bill_limit_modifies_only_selected_device_and_confirms_readback(self):
        after = {**SETTINGS, "devices": [{"deviceId": "device-private", "energyQuotaAmount": 25, "energyQuotaStatus": "enable"}, SETTINGS["devices"][1]]}
        self.api.request = AsyncMock(side_effect=[SETTINGS, {}, after])
        result = await self.api.set_bill_limit("home-private", "device-private", 25, True)
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.api.request.await_args_list[1].args, ("POST", "/energymanagement/setting/quota", {
            "home": None, "devices": [{"deviceId": "device-private", "energyQuotaAmount": 25, "energyQuotaStatus": "enable"}]}))
        self.assertNotIn("private", str(result))

    async def test_accepted_but_unchanged_bill_setting_is_not_confirmed(self):
        self.api.request = AsyncMock(side_effect=[SETTINGS, {}, SETTINGS])
        result = await self.api.set_bill_limit("home-private", "device-private", 25, True)
        self.assertFalse(result["readback_confirmed"])
        self.assertEqual(self.api.request.await_count, 3)  # No automatic replay.

    async def test_unknown_device_is_never_added_by_a_limit_change(self):
        self.api.request = AsyncMock(return_value=SETTINGS)
        with self.assertRaises(ApiError): await self.api.set_bill_limit("home-private", "unknown", 5, True)
        self.assertEqual(self.api.request.await_count, 1)

    async def test_price_payload_does_not_overwrite_quota_or_subscriber_type(self):
        after = {**SETTINGS, "home": {**SETTINGS["home"], "kwhPrice": 4}}
        self.api.request = AsyncMock(side_effect=[{}, after])
        result = await self.api.set_energy_price("home-private", 4, "TRY")
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.api.request.await_args_list[0].args, ("POST", "/energymanagement/setting/pricingInfo",
            {"home": {"homeId": "home-private", "kwhPrice": 4, "currencyShortCode": "TRY"}}))

    async def test_nonfinite_negative_and_boolean_amounts_never_reach_network(self):
        self.api.request = AsyncMock()
        for amount in (float("nan"), float("inf"), -1, True, "4"):
            with self.subTest(amount=amount), self.assertRaises(ApiError):
                await self.api.set_energy_price("home", amount, "TRY")
        self.api.request.assert_not_awaited()

    async def test_invalid_currency_never_reaches_network(self):
        self.api.request = AsyncMock()
        with self.assertRaises(ApiError): await self.api.set_energy_price("home", 4, "TRY&extra=x")
        self.api.request.assert_not_awaited()

    def test_settings_response_excludes_account_and_other_device_identifiers(self):
        view = self.api.billing_view(SETTINGS, "device-private")
        self.assertNotIn("private", str(view))
        self.assertEqual(view["device"]["energyQuotaAmount"], 50)

    async def test_home_quota_does_not_send_any_device_changes(self):
        after = {**SETTINGS, "home": {**SETTINGS["home"], "energyQuotaAmount": 330, "energyQuotaStatus": "enable"}}
        self.api.request = AsyncMock(side_effect=[{}, after])
        result = await self.api.set_home_bill_limit("home-private", 330, True)
        self.assertTrue(result["readback_confirmed"])
        self.assertEqual(self.api.request.await_args_list[0].args, ("POST", "/energymanagement/setting/quota", {
            "home": {"homeId": "home-private", "energyQuotaAmount": 330, "energyQuotaStatus": "enable"}, "devices": None}))

    async def test_tariff_options_write_only_the_selected_field_and_match_readback(self):
        cases = [("subscriber_type", "business", "subscriberType", "subscriberType"),
                 ("tariff_type", "three-time", "tariffType", "tariffType"),
                 ("energy_management", "disable", "status", "energyManagement")]
        for option, value, endpoint, field in cases:
            with self.subTest(option=option):
                after = {**SETTINGS, "home": {**SETTINGS["home"], field: value}}
                self.api.request = AsyncMock(side_effect=[{}, after])
                result = await self.api.set_billing_option("home-private", option, value)
                self.assertTrue(result["readback_confirmed"])
                self.assertEqual(self.api.request.await_args_list[0].args, ("POST", "/energymanagement/setting/" + endpoint,
                    {"home": {"homeId": "home-private", field: value}}))
                self.assertNotIn("private", str(result))

    async def test_unchanged_tariff_is_not_confirmed_and_never_retried(self):
        self.api.request = AsyncMock(side_effect=[{}, SETTINGS])
        result = await self.api.set_billing_option("home-private", "tariff_type", "three-time")
        self.assertFalse(result["readback_confirmed"])
        self.assertEqual(self.api.request.await_count, 2)

    async def test_unknown_tariff_values_never_reach_network(self):
        self.api.request = AsyncMock()
        for option, value in (("tariff_type", "free"), ("subscriber_type", "root"), ("energy_management", True), ("arbitrary/path", "enable")):
            with self.subTest(option=option), self.assertRaises(ApiError):
                await self.api.set_billing_option("home", option, value)
        self.api.request.assert_not_awaited()

    async def test_fractional_and_out_of_range_limits_are_not_rounded_or_sent(self):
        self.api.request = AsyncMock()
        for amount in (1.5, 2147483648, -1, True):
            with self.subTest(amount=amount), self.assertRaises(ApiError):
                await self.api.set_home_bill_limit("home", amount, True)
        self.api.request.assert_not_awaited()

class EnergyTests(unittest.IsolatedAsyncioTestCase):
    def test_missing_and_invalid_samples_are_unknown_but_zero_is_real(self):
        self.assertIsNone(sample_value(None, "energyAmount"))
        self.assertIsNone(sample_value({"samples": []}, "energyAmount"))
        for value in (None, True, float("nan"), "3.25"):
            self.assertIsNone(sample_value({"samples": [{"consumption": {"energyAmount": value}}]}, "energyAmount"))
        self.assertEqual(sample_value({"samples": [{"consumption": {"energyAmount": 0}}]}, "energyAmount"), 0)

    async def test_one_failed_device_or_period_does_not_hide_other_energy_values(self):
        api = types.SimpleNamespace(consumption=AsyncMock(), billing_settings=AsyncMock(side_effect=ApiError("offline")))
        async def read(home, uuid, period, count):
            if uuid == "one" and period == "day": raise ApiError("unavailable")
            return {"samples": [{"date": "11.2026", "consumption": {"energyAmount": 2}}]}
        api.consumption.side_effect = read
        c = EnergyCoordinator(None, types.SimpleNamespace(data={"home_id": "home"}),
                              types.SimpleNamespace(api=api, data={"one": None, "two": None}))
        result = await c._async_update_data()
        self.assertIsNone(result["one"]["day"])
        self.assertEqual(sample_value(result["one"]["month"], "energyAmount"), 2)
        self.assertEqual(sample_value(result["two"]["day"], "energyAmount"), 2)
        self.assertIsNone(c.billing)

if __name__ == "__main__": unittest.main()
