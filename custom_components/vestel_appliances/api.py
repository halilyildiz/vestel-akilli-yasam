"""Vestel cloud transport. No dependency on another custom integration.

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

API_BASE = "https://sh-native-api.homevsmart.com/v1.0"
COGNITO = "https://cognito-idp.eu-west-1.amazonaws.com/"
CLIENT_ID = "6tl8koi5fis9j7i3u3jnv15vr7"
CLIENT_SECRET = "mc4j2r13mctk8u46poaic9snm83khk458c8a1uupk6sqoqar90c"


class ApiError(Exception):
    pass


class AuthError(ApiError):
    pass


class Api:
    def __init__(self, session, credentials, token_callback=None):
        self.session = session
        self.credentials = dict(credentials)
        self.token_callback = token_callback
        self._token = None
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
                if response.status != 200:
                    raise AuthError(f"Vestel oturumu yenilenemedi (HTTP {response.status}).")
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ApiError("Vestel kimlik sunucusuna ulaşılamadı.") from None
        result = body.get("AuthenticationResult")
        if not result or not result.get("IdToken"):
            raise AuthError("Vestel hesabıyla yeniden giriş gerekiyor.")
        self._token = result["IdToken"]
        self._expires = time.monotonic() + float(result.get("ExpiresIn", 3600)) - 120
        if result.get("RefreshToken"):
            self.credentials["refresh_token"] = result["RefreshToken"]
            if self.token_callback:
                self.token_callback(result["RefreshToken"])

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
                raise AuthError("Vestel hesabıyla yeniden giriş gerekiyor.")
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
                        raise AuthError("Vestel oturumu reddedildi.")
                    if response.status >= 400:
                        raise ApiError(f"Vestel isteği başarısız (HTTP {response.status}).")
                    body = await response.json(content_type=None)
                    if not isinstance(body, dict):
                        raise ApiError("Vestel yanıtının biçimi beklenenden farklı.")
                    return body
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                raise ApiError("Vestel sunucusundan yanıt alınamadı.") from None
        raise AuthError("Vestel oturumu reddedildi.")

    async def homes(self) -> dict[str, str]:
        """Read the account's homes (APK HomesApi.k / GetHomesResponseNetworkDTO)."""
        body = await self.request("GET", "/homes")
        items = body.get("items")
        if not isinstance(items, list):
            raise ApiError("Vestel ev listesi okunamadı.")
        homes: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ApiError("Vestel ev listesinde geçersiz kayıt var.")
            home_id = item.get("homeId")
            if not isinstance(home_id, str) or not home_id.strip():
                raise ApiError("Vestel ev kimliği okunamadı.")
            name = item.get("homeName")
            homes[home_id] = name if isinstance(name, str) and name.strip() else "Ev"
        return homes

    async def devices(self, home_id):
        body = await self.request("GET", f"/homes/{quote(home_id, safe='')}/devices")
        items = (body.get("items") or {}).get("homeappliances")
        if not isinstance(items, list):
            raise ApiError("Vestel cihaz listesi okunamadı.")
        return items

    async def discovery(self, device_id):
        body = await self.request("GET", "/device/discovery?uuid=" + quote(device_id, safe=""))
        data = body.get("data")
        if not isinstance(data, dict) or not data.get("deviceType"):
            raise ApiError("Cihazın özellik tanımı okunamadı.")
        return data

    async def status(self, device_id):
        body = await self.request("GET", "/homeappliances/legacy/status?uuid=" + quote(device_id, safe=""))
        data = body.get("data")
        if not isinstance(data, dict):
            raise ApiError("Cihaz durumu okunamadı.")
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
            raise ApiError("Vestel komutu kabul etmedi.")

    async def consumption(self, home_id, device_id, period="month", count=12):
        """Read-only query, despite POST: verified APK EnergyManagementApi.e.

        Amounts are the app's estimates, not a cumulative meter reading.
        Preserve the original dated samples and never invent missing values.
        """
        if period not in {"day", "week", "month"} or type(count) is not int or not 1 <= count <= 366:
            raise ApiError("Geçersiz tüketim sorgusu aralığı.")
        body = await self.request("POST",
            f"/energymanagement/consumption/{period}?count={count}&queryType=device",
            {"homeId": home_id, "deviceId": device_id})
        data = body.get("data", body)
        if not isinstance(data, dict) or not isinstance(data.get("deviceConsumption"), list):
            raise ApiError("Tüketim geçmişi yanıtı beklenen biçimde değil.")
        samples = []
        for sample in data["deviceConsumption"]:
            if not isinstance(sample, dict) or not isinstance(sample.get("consumption"), dict):
                raise ApiError("Tüketim geçmişinde geçersiz kayıt var.")
            samples.append({"date": sample.get("date"), "consumption": {
                k: sample["consumption"].get(k) for k in ("energyAmount", "energyCost", "water")}})
        return {"period": period, "estimated": True,
                "currencyShortCode": data.get("currencyShortCode"),
                "currencySymbol": data.get("currencySymbol"), "samples": samples}

    async def billing_settings(self, home_id):
        body = await self.request("GET", "/energymanagement/setting/home/" + quote(home_id, safe=""))
        data = body.get("data", body)
        if not isinstance(data, dict) or not isinstance(data.get("home"), dict) or not isinstance(data.get("devices"), list):
            raise ApiError("Akıllı Fatura ayarları okunamadı.")
        return data

    async def _identity_request(self, operation, payload):
        """Existing authenticated Cognito role only; no policy/role changes."""
        if operation not in {"GetId", "GetCredentialsForIdentity"}:
            raise ApiError("Desteklenmeyen kimlik işlemi.")
        try:
            async with self.session.post("https://cognito-identity.eu-west-1.amazonaws.com/",
                json=payload, headers={"Content-Type": "application/x-amz-json-1.1",
                    "X-Amz-Target": "AWSCognitoIdentityService." + operation},
                timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise ApiError(f"Canlı veri kimliği alınamadı (HTTP {response.status}).")
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise ApiError("Canlı veri kimlik sunucusuna ulaşılamadı.") from None
        if not isinstance(body, dict):
            raise ApiError("Canlı veri kimlik yanıtı geçersiz.")
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
                    raise ApiError("Canlı veri kimliği geçersiz.")
            body = await self._identity_request("GetCredentialsForIdentity", {
                "IdentityId": self._iot_identity, "Logins": logins})
            credentials = body.get("Credentials")
            if not isinstance(credentials, dict):
                raise ApiError("Geçici canlı veri kimlik bilgisi bulunamadı.")
            if not all(isinstance(credentials.get(k), str) and credentials[k]
                       for k in ("AccessKeyId", "SecretKey", "SessionToken")):
                raise ApiError("Geçici canlı veri kimlik bilgisi eksik.")
            expiration = credentials.get("Expiration")
            if isinstance(expiration, bool) or not isinstance(expiration, (int, float)) or expiration <= time.time() + 60:
                raise ApiError("Geçici canlı veri kimlik bilgisinin süresi geçersiz.")
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
            raise ApiError("Sıfır veya pozitif, sonlu bir tutar girin.")
        return value

    @classmethod
    def _quota_amount(cls, value):
        value = cls._amount(value)
        # APK quota DTOs are signed 32-bit integers; do not silently round.
        if value != int(value) or value > 2147483647:
            raise ApiError("Fatura limiti 0–2147483647 aralığında tam sayı olmalı.")
        return int(value)

    async def set_bill_limit(self, home_id, device_id, amount, enabled):
        amount = self._quota_amount(amount)
        if type(enabled) is not bool:
            raise ApiError("Limit durumu açık veya kapalı olmalı.")
        status = "enable" if enabled else "disable"
        async with self._billing_lock:
            # Confirm membership before modifying an existing device setting.
            before = await self.billing_settings(home_id)
            if not any(d.get("deviceId") == device_id for d in before["devices"]):
                raise ApiError("Cihaz için fatura limiti ayarı bulunamadı.")
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
            raise ApiError("Üç harfli para birimi kodu girin; örneğin TRY.")
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
            raise ApiError("Limit durumu açık veya kapalı olmalı.")
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
            raise ApiError("Desteklenmeyen fatura ayarı.")
        endpoint, field, allowed = options[option]
        if not isinstance(value, str) or value not in allowed:
            raise ApiError("Desteklenmeyen fatura ayarı değeri.")
        async with self._billing_lock:
            await self.request("POST", "/energymanagement/setting/" + endpoint,
                {"home": {"homeId": home_id, field: value}})
            actual = (await self.billing_settings(home_id))["home"].get(field)
            return {"accepted": True, "readback_confirmed": actual == value, "home": {field: actual}}
