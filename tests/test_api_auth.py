"""Authentication error classification through the transport and its callers."""
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import test_coordinator  # noqa: F401 -- initialize the shared minimal HA runtime
from custom_components.vestel_appliances import api as api_module
from custom_components.vestel_appliances.api import Api, ApiError, AuthError
from custom_components.vestel_appliances.coordinator import Coordinator
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        timeout = patch.object(api_module.aiohttp, "ClientTimeout", create=True)
        timeout.start()
        self.addCleanup(timeout.stop)
        self.session = MagicMock()
        self.api = Api(self.session, {
            "email": "example@example.com", "password": "test-only",
            "refresh_token": "test-refresh-token",
        })

    def response(self, status, body=None):
        response = MagicMock(status=status)
        response.json = AsyncMock(return_value=body)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=False)
        return context

    async def test_transient_http_errors_do_not_fallback_to_password(self):
        for status in (429, 500, 502, 503, 504, 599):
            with self.subTest(status=status):
                self.session.post.reset_mock()
                self.session.post.return_value = self.response(status)
                with self.assertRaises(ApiError) as caught:
                    await self.api.token()
                self.assertNotIsInstance(caught.exception, AuthError)
                self.session.post.assert_called_once()
                self.assertEqual(self.api.credentials["refresh_token"], "test-refresh-token")

    async def test_cognito_transient_http_400_errors_do_not_fallback(self):
        for error_type in (
            "TooManyRequestsException", "InternalErrorException",
            "com.amazonaws.cognito#TooManyRequestsException",
        ):
            with self.subTest(error_type=error_type):
                self.session.post.reset_mock()
                self.session.post.return_value = self.response(400, {"__type": error_type})
                with self.assertRaises(ApiError) as caught:
                    await self.api.token()
                self.assertNotIsInstance(caught.exception, AuthError)
                self.session.post.assert_called_once()

    async def test_rejected_credentials_remain_auth_errors(self):
        for status, body in (
            (400, {"__type": "NotAuthorizedException"}), (401, {}), (403, {}),
        ):
            with self.subTest(status=status):
                self.session.post.return_value = self.response(status, body)
                with self.assertRaises(AuthError):
                    await self.api._auth("InitiateAuth", {})

    async def test_invalid_refresh_token_still_allows_password_login(self):
        self.session.post.side_effect = [
            self.response(400, {"__type": "NotAuthorizedException"}),
            self.response(200, {"AuthenticationResult": {
                "IdToken": "test-id-token", "RefreshToken": "new-test-refresh-token",
                "ExpiresIn": 3600,
            }}),
        ]
        self.assertEqual(await self.api.token(), "test-id-token")
        self.assertEqual(self.session.post.call_count, 2)
        self.assertEqual(self.api.credentials["refresh_token"], "new-test-refresh-token")

    async def test_transient_password_login_failure_is_not_invalid_auth(self):
        self.api.credentials.pop("refresh_token")
        self.session.post.return_value = self.response(503)
        with self.assertRaises(ApiError) as caught:
            await self.api.token()
        self.assertNotIsInstance(caught.exception, AuthError)
        self.session.post.assert_called_once()

    async def test_polling_reports_transient_failure_without_reauthentication(self):
        self.session.post.return_value = self.response(503)
        coordinator = Coordinator(None, types.SimpleNamespace(data={"home_id": "test-home"}), self.api)
        with self.assertRaises(UpdateFailed) as caught:
            await coordinator._async_update_data()
        self.assertNotIsInstance(caught.exception, ConfigEntryAuthFailed)

    async def test_login_form_reports_transient_failure_as_cannot_connect(self):
        from test_config_flow import load_flow

        self.session.post.return_value = self.response(429)
        module = load_flow()
        flow = module.Flow()
        flow.hass = object()
        with patch.object(module, "Api", return_value=self.api):
            result = await flow.async_step_user({"email": "example@example.com", "password": "test-only"})
        self.assertEqual(result["errors"]["base"], "cannot_connect")
