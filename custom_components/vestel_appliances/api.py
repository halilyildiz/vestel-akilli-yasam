"""Vestel cloud transport. No dependency on another custom integration.

Adapted from mehmetaktas/ha-vestel-smarthome (MIT),
copyright (c) 2026 Mehmet Aktaş. See the accompanying LICENSE and NOTICE.md.

Endpoints/authentication verified against the installed Vestel Smart Home
0.1.2 source and the user's read-only discovery capture.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import hmac
import math
import re
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from .errors import LocalizedError

API_BASE = "https://sh-native-api.homevsmart.com/v1.0"
COGNITO = "https://cognito-idp.eu-west-1.amazonaws.com/"
CLIENT_ID = "6tl8koi5fis9j7i3u3jnv15vr7"
CLIENT_SECRET = "mc4j2r13mctk8u46poaic9snm83khk458c8a1uupk6sqoqar90c"


class ApiError(LocalizedError):
    pass


class AuthError(ApiError):
    pass


class Api:
    def __init__(self, session, credentials, token_callback=None):
        self.session = session
        self.credentials = dict(credentials)
        self.token_callback = token_callback
        self._token = None
        self.inventory_summary: dict[str, int] = {}
        self._expires = 0
        self._auth_lock = asyncio.Lock()
        self._billing_lock = asyncio.Lock()
        self._iot_lock = asyncio.Lock()
        self._iot_identity = None
        self._iot_credentials = None

    async def _auth(self, flow, payload):
        try:
            async with self.session.post(COGNITO, json=payload, headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": "AWSCognitoIdentityProviderService." + flow,
            }, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 429 or 500 <= response.status < 600:
                    raise ApiError('auth_server_http', placeholders={"http_status": str(response.status)})
                if response.status != 200:
                    # Cognito can report throttling as HTTP 400 rather than 429.
                    # Keep transient failures out of the password fallback and
                    # Home Assistant's reauthentication flow.
                    if response.status == 400:
                        try:
                            error = await response.json(content_type=None)
                        except ValueError:
                            error = {}
                        error_type = error.get("__type", "") if isinstance(error, dict) else ""
                        if isinstance(error_type, str) and error_type.rsplit("#", 1)[-1] in {
                            "TooManyRequestsException", "InternalErrorException",
                        }:
                            raise ApiError('auth_server_unavailable')
                    raise AuthError('auth_rejected_http', placeholders={"http_status": str(response.status)})
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise ApiError('auth_connection_failed') from None
        if not isinstance(body, dict):
            raise ApiError('auth_response_invalid')
        result = body.get("AuthenticationResult")
        if result is None and isinstance(body.get("ChallengeName"), str) and body["ChallengeName"]:
            raise AuthError('reauth_required')
        if not isinstance(result, dict):
            raise ApiError('auth_result_invalid')
        token = result.get("IdToken")
        if not isinstance(token, str) or not token.strip():
            raise ApiError('auth_token_invalid')
        duration = result.get("ExpiresIn", 3600)
        try:
            if isinstance(duration, bool) or not isinstance(duration, (int, float, str)):
                raise ValueError
            duration = float(duration)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError
        except (ValueError, OverflowError):
            raise ApiError('auth_expiry_invalid') from None
        refresh = result.get("RefreshToken")
        if "RefreshToken" in result and (not isinstance(refresh, str) or not refresh.strip()):
            raise ApiError('refresh_token_invalid')
        # Validate the entire response before changing any cached credentials.
        self._token = token
        self._expires = time.monotonic() + duration - 120
        if refresh is not None:
            self.credentials["refresh_token"] = refresh
            if self.token_callback:
                self.token_callback(refresh)

    async def token(self):
        async with self._auth_lock:
            if self._token and time.monotonic() < self._expires:
                return self._token
            refresh = self.credentials.get("refresh_token")
            if refresh:
                try:
                    await self._auth("GetTokensFromRefreshToken", {
                        "ClientId": CLIENT_ID, "ClientSecret": CLIENT_SECRET,
                        "RefreshToken": refresh, "ClientMetadata": {},
                    })
                    return self._token
                except AuthError:
                    if not self.credentials.get("password"):
                        raise
            email = self.credentials.get("email", "")
            password = self.credentials.get("password")
            if not email or not password:
                raise AuthError('reauth_required')
            secret_hash = base64.b64encode(hmac.new(CLIENT_SECRET.encode(),
                (email + CLIENT_ID).encode(), hashlib.sha256).digest()).decode()
            await self._auth("InitiateAuth", {"AuthFlow": "USER_PASSWORD_AUTH",
                "ClientId": CLIENT_ID, "AuthParameters": {"USERNAME": email,
                "PASSWORD": password, "SECRET_HASH": secret_hash}})
            return self._token

    async def request(self, method, path, payload=None):
        for attempt in range(2):
            token = await self.token()
            try:
                async with self.session.request(method, API_BASE + path, json=payload,
                    headers={"Token": token, "Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status in (401, 403):
                        self._expires = 0
                        if attempt == 0:
                            continue
                        raise AuthError('session_rejected')
                    if response.status >= 400:
                        raise ApiError('request_http', placeholders={"http_status": str(response.status)})
                    body = await response.json(content_type=None)
                    if not isinstance(body, dict):
                        raise ApiError('cloud_response_invalid')
                    return body
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                raise ApiError('cloud_connection_failed') from None
        raise AuthError('session_rejected')

    async def homes(self) -> dict[str, str]:
        """Read the account's homes (APK HomesApi.k / GetHomesResponseNetworkDTO)."""
        body = await self.request("GET", "/homes")
        items = body.get("items")
        if not isinstance(items, list):
            raise ApiError('homes_invalid')
        homes: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ApiError('home_record_invalid')
            home_id = item.get("homeId")
            if not isinstance(home_id, str) or not home_id.strip():
                raise ApiError('home_id_invalid')
            name = item.get("homeName")
            homes[home_id] = name if isinstance(name, str) and name.strip() else "Home"
        return homes

    async def devices(self, home_id):
        body = await self.request("GET", f"/homes/{quote(home_id, safe='')}/devices")
        container = body.get("items")
        if not isinstance(container, dict):
            raise ApiError('devices_invalid')
        items = container.get("homeappliances")
        if not isinstance(items, list):
            raise ApiError('devices_invalid')
        # APK GetDevicesResponseNetworkDTO.Items separates these backends.
        # Counts aid compatibility reports; third-party records never enter
        # the legacy register transport and no IDs/credentials are retained.
        self.inventory_summary = {
            key: len(container[key]) for key in (
                "homeappliances", "nonSmartDevices", "televisions", "pairedDevices",
                "partnerDevices", "chargers", "thirdpartyDevices",
            ) if isinstance(container.get(key), list)
        }
        return items

    async def discovery(self, device_id):
        body = await self.request("GET", "/device/discovery?uuid=" + quote(device_id, safe=""))
        data = body.get("data")
        if not isinstance(data, dict) or not data.get("deviceType"):
            raise ApiError('discovery_invalid')
        return data

    async def status(self, device_id):
        body = await self.request("GET", "/homeappliances/legacy/status?uuid=" + quote(device_id, safe=""))
        data = body.get("data")
        if not isinstance(data, dict):
            raise ApiError('status_invalid')
        return data

    async def send(self, device, code):
        import json
        uuid = device["deviceId"]
        body = await self.request("POST", f"/customer/devices/{quote(uuid, safe='')}/legacy/command", {
            "brand": str(device.get("oemBrand") or "Vestel").capitalize(),
            "device_type": device["deviceType"], "wifi_card_type": device["wifiCardType"],
            "message": json.dumps({"cmd": f"c:{uuid},{code}"}),
        })
        if str(body.get("message", "")).lower() != "success":
            raise ApiError('command_rejected')

    async def consumption(self, home_id, device_id, period="month", count=12):
        """Read-only query, despite POST: verified APK EnergyManagementApi.e.

        Amounts are the app's estimates, not a cumulative meter reading.
        Preserve the original dated samples and never invent missing values.
        """
        if period not in {"day", "week", "month"} or type(count) is not int or not 1 <= count <= 366:
            raise ApiError('consumption_range_invalid')
        body = await self.request("POST",
            f"/energymanagement/consumption/{period}?count={count}&queryType=device",
            {"homeId": home_id, "deviceId": device_id})
        data = body.get("data", body)
        if not isinstance(data, dict) or not isinstance(data.get("deviceConsumption"), list):
            raise ApiError('consumption_response_invalid')
        samples = []
        for sample in data["deviceConsumption"]:
            if not isinstance(sample, dict) or not isinstance(sample.get("consumption"), dict):
                raise ApiError('consumption_record_invalid')
            samples.append({"date": sample.get("date"), "consumption": {
                k: sample["consumption"].get(k) for k in ("energyAmount", "energyCost", "water")}})
        return {"period": period, "estimated": True,
                "currencyShortCode": data.get("currencyShortCode"),
                "currencySymbol": data.get("currencySymbol"), "samples": samples}

    async def billing_settings(self, home_id):
        body = await self.request("GET", "/energymanagement/setting/home/" + quote(home_id, safe=""))
        data = body.get("data", body)
        if (not isinstance(data, dict) or not isinstance(data.get("home"), dict)
                or not isinstance(data.get("devices"), list)
                or any(not isinstance(device, dict) for device in data["devices"])):
            raise ApiError('billing_settings_invalid')
        return data

    async def _identity_request(self, operation, payload):
        """Existing authenticated Cognito role only; no policy/role changes."""
        if operation not in {"GetId", "GetCredentialsForIdentity"}:
            raise ApiError('identity_operation_unsupported')
        try:
            async with self.session.post("https://cognito-identity.eu-west-1.amazonaws.com/",
                json=payload, headers={"Content-Type": "application/x-amz-json-1.1",
                    "X-Amz-Target": "AWSCognitoIdentityService." + operation},
                timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise ApiError('identity_http', placeholders={"http_status": str(response.status)})
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise ApiError('identity_connection_failed') from None
        if not isinstance(body, dict):
            raise ApiError('identity_response_invalid')
        return body

    async def iot_credentials(self):
        # Pool/provider are public APK configuration, not a new account/role.
        async with self._iot_lock:
            cached = self._iot_credentials
            if cached and cached["expiration"] > time.time() + 180:
                return cached
            logins = {"cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EgDdXOayO": await self.token()}
            if self._iot_identity is None:
                body = await self._identity_request("GetId", {
                    "IdentityPoolId": "eu-west-1:bb1ff9a2-6db0-4f3f-b630-62a9fc3bfbda", "Logins": logins})
                self._iot_identity = body.get("IdentityId")
                if not isinstance(self._iot_identity, str) or not self._iot_identity.startswith("eu-west-1:"):
                    self._iot_identity = None
                    raise ApiError('identity_invalid')
            body = await self._identity_request("GetCredentialsForIdentity", {
                "IdentityId": self._iot_identity, "Logins": logins})
            credentials = body.get("Credentials")
            if not isinstance(credentials, dict):
                raise ApiError('iot_credentials_missing')
            if not all(isinstance(credentials.get(k), str) and credentials[k]
                       for k in ("AccessKeyId", "SecretKey", "SessionToken")):
                raise ApiError('iot_credentials_incomplete')
            expiration = credentials.get("Expiration")
            if isinstance(expiration, bool) or not isinstance(expiration, (int, float)) or expiration <= time.time() + 60:
                raise ApiError('iot_expiry_invalid')
            self._iot_credentials = {"access_key": credentials["AccessKeyId"],
                "secret_key": credentials["SecretKey"], "session_token": credentials["SessionToken"],
                "expiration": expiration}
            return self._iot_credentials

    @staticmethod
    def billing_view(settings, device_id):
        """Only expose this device's settings and public home pricing fields."""
        home = settings["home"]
        device = next((d for d in settings["devices"] if d.get("deviceId") == device_id), {})
        return {"home": {k: home.get(k) for k in ("energyManagement", "energyQuotaAmount",
                    "energyQuotaStatus", "subscriberType", "tariffType", "kwhPrice", "currencyShortCode")},
                "device": {k: device.get(k) for k in ("energyQuotaAmount", "energyQuotaStatus")}}

    @staticmethod
    def _amount(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ApiError('amount_invalid')
        return value

    @classmethod
    def _quota_amount(cls, value):
        value = cls._amount(value)
        # APK quota DTOs are signed 32-bit integers; do not silently round.
        if value != int(value) or value > 2147483647:
            raise ApiError('quota_invalid')
        return int(value)

    async def set_bill_limit(self, home_id, device_id, amount, enabled):
        amount = self._quota_amount(amount)
        if type(enabled) is not bool:
            raise ApiError('limit_enabled_invalid')
        status = "enable" if enabled else "disable"
        async with self._billing_lock:
            # Confirm membership before modifying an existing device setting.
            before = await self.billing_settings(home_id)
            if not any(d.get("deviceId") == device_id for d in before["devices"]):
                raise ApiError('quota_device_missing')
            await self.request("POST", "/energymanagement/setting/quota", {"home": None,
                "devices": [{"deviceId": device_id, "energyQuotaAmount": amount, "energyQuotaStatus": status}]})
            after = self.billing_view(await self.billing_settings(home_id), device_id)["device"]
            actual = after.get("energyQuotaAmount")
            confirmed = (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                         and math.isclose(actual, amount) and after.get("energyQuotaStatus") == status)
            return {"accepted": True, "readback_confirmed": confirmed, "device": after}

    async def set_energy_price(self, home_id, price, currency):
        price = self._amount(price)
        if not isinstance(currency, str) or re.fullmatch(r"[A-Z]{3}", currency) is None:
            raise ApiError('currency_invalid')
        async with self._billing_lock:
            await self.request("POST", "/energymanagement/setting/pricingInfo",
                {"home": {"homeId": home_id, "kwhPrice": price, "currencyShortCode": currency}})
            home = (await self.billing_settings(home_id))["home"]
            actual = home.get("kwhPrice")
            confirmed = (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                         and math.isclose(actual, price) and home.get("currencyShortCode") == currency)
            return {"accepted": True, "readback_confirmed": confirmed,
                    "kwhPrice": actual, "currencyShortCode": home.get("currencyShortCode")}

    async def set_home_bill_limit(self, home_id, amount, enabled):
        amount = self._quota_amount(amount)
        if type(enabled) is not bool:
            raise ApiError('limit_enabled_invalid')
        status = "enable" if enabled else "disable"
        async with self._billing_lock:
            await self.request("POST", "/energymanagement/setting/quota", {
                "home": {"homeId": home_id, "energyQuotaAmount": amount, "energyQuotaStatus": status},
                "devices": None})
            home = (await self.billing_settings(home_id))["home"]
            actual = home.get("energyQuotaAmount")
            confirmed = (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                         and math.isclose(actual, amount) and home.get("energyQuotaStatus") == status)
            return {"accepted": True, "readback_confirmed": confirmed,
                    "home": {"energyQuotaAmount": actual, "energyQuotaStatus": home.get("energyQuotaStatus")}}

    async def set_billing_option(self, home_id, option, value):
        # DTOs and serialized enum values verified in the supplied APK.
        options = {
            "subscriber_type": ("subscriberType", "subscriberType", {"residential", "business", "industrial"}),
            "tariff_type": ("tariffType", "tariffType", {"one-time", "three-time"}),
            "energy_management": ("status", "energyManagement", {"enable", "disable"}),
        }
        if option not in options:
            raise ApiError('billing_option_unsupported')
        endpoint, field, allowed = options[option]
        if not isinstance(value, str) or value not in allowed:
            raise ApiError('billing_value_unsupported')
        async with self._billing_lock:
            await self.request("POST", "/energymanagement/setting/" + endpoint,
                {"home": {"homeId": home_id, field: value}})
            actual = (await self.billing_settings(home_id))["home"].get(field)
            return {"accepted": True, "readback_confirmed": actual == value, "home": {field: actual}}
