"""Test auth isolation, subscription scope, cancellation and burst coalescing."""
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import json
import time
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit
import test_coordinator  # noqa: F401 -- initialize shared HA test stubs
from custom_components.vestel_appliances.api import Api, ApiError
from custom_components.vestel_appliances.live import LiveUpdates
from custom_components.vestel_appliances.mqtt_protocol import subscription_topics, websocket_path

CREDS = {"access_key": "TESTKEY", "secret_key": "secret-never-log", "session_token": "token/+==", "expiration": time.time() + 3600}

class SigningTests(unittest.TestCase):
    def test_iot_session_token_is_added_after_signing_and_encoded_once(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        one = parse_qs(urlsplit(websocket_path(CREDS, now)).query)
        two = parse_qs(urlsplit(websocket_path({**CREDS, "session_token": "another-token"}, now)).query)
        self.assertEqual(one["X-Amz-Signature"], two["X-Amz-Signature"])
        self.assertEqual(one["X-Amz-Security-Token"], ["token/+=="])
        self.assertEqual(one["X-Amz-Credential"], ["TESTKEY/20261122/eu-west-1/iotdevicegateway/aws4_request"])
        self.assertEqual(one["X-Amz-Expires"], ["900"])
        self.assertNotIn(CREDS["secret_key"], websocket_path(CREDS, now))

    def test_only_exact_device_shadow_channels_are_subscribed(self):
        devices = {uuid: types.SimpleNamespace(metadata={"pubTopic": "account/#"})
                   for uuid in ("device-one", "device-two", "evil/#", "bad+", "bad/segment")}
        result = subscription_topics(devices)
        self.assertEqual(set(result), {"$aws/things/device-one/shadow/update/accepted", "$aws/things/device-two/shadow/update/accepted"})
        self.assertTrue(all("#" not in key and "+" not in key for key in result))

class IdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_credentials_use_existing_authenticated_role_and_are_cached(self):
        api = Api(None, {})
        api.token = AsyncMock(return_value="private-id-token")
        api._identity_request = AsyncMock(side_effect=[{"IdentityId": "eu-west-1:test-identity"}, {"Credentials": {
            "AccessKeyId": "access", "SecretKey": "secret", "SessionToken": "session", "Expiration": time.time() + 3600}}])
        first = await api.iot_credentials()
        self.assertEqual(await api.iot_credentials(), first)
        self.assertEqual([call.args[0] for call in api._identity_request.await_args_list], ["GetId", "GetCredentialsForIdentity"])
        self.assertTrue(all("Logins" in call.args[1] for call in api._identity_request.await_args_list))
        self.assertNotIn("CustomRoleArn", str(api._identity_request.await_args_list))

    async def test_expired_credentials_are_not_reused(self):
        api = Api(None, {})
        api.token = AsyncMock(return_value="id")
        api._iot_identity = "eu-west-1:existing"
        api._iot_credentials = {**CREDS, "expiration": time.time() - 1}
        api._identity_request = AsyncMock(return_value={"Credentials": {"AccessKeyId": "new", "SecretKey": "secret", "SessionToken": "session", "Expiration": time.time() + 3600}})
        self.assertEqual((await api.iot_credentials())["access_key"], "new")
        self.assertEqual(api._identity_request.await_args.args[0], "GetCredentialsForIdentity")

    async def test_expired_or_missing_credential_response_is_rejected(self):
        api = Api(None, {}); api._iot_identity = "eu-west-1:existing"
        api.token = AsyncMock(return_value="id")
        api._identity_request = AsyncMock(return_value={"Credentials": {}})
        with self.assertRaises(ApiError): await api.iot_credentials()
        self.assertIsNone(api._iot_credentials)

class LiveTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.coordinator = types.SimpleNamespace(data={"device": types.SimpleNamespace(metadata={})},
            api=types.SimpleNamespace(iot_credentials=AsyncMock(return_value=CREDS)),
            async_request_refresh=AsyncMock(), async_update_listeners=Mock())
        self.live = LiveUpdates(types.SimpleNamespace(async_add_executor_job=AsyncMock(return_value=None)), None, self.coordinator)
        self.topics = subscription_topics(self.coordinator.data)
        self.topic = next(iter(self.topics))

    def test_unknown_retained_and_oversize_messages_do_not_invalidate(self):
        self.live.notify("unrelated", b"{}", False, self.topics)
        self.live.notify(self.topic, b"{}", True, self.topics)
        self.live.notify(self.topic, b"x" * 262145, False, self.topics)
        self.assertFalse(self.live._pending.is_set())
        self.assertEqual(self.live.stats["messages_received"], 0)

    async def test_a_burst_causes_one_rest_refresh_without_applying_payload_registers(self):
        done = asyncio.Event()
        async def refresh(): done.set()
        self.coordinator.async_request_refresh.side_effect = refresh
        for _ in range(100): self.live.notify(self.topic, b'{"ACGENSI":"00001"}', False, self.topics)
        with patch("custom_components.vestel_appliances.live.asyncio.sleep", new=AsyncMock()):
            task = asyncio.create_task(self.live._refresh_worker())
            await asyncio.wait_for(done.wait(), 2)
            task.cancel()
            with suppress(asyncio.CancelledError): await task
        self.assertEqual(self.live.stats["messages_received"], 100)
        self.coordinator.async_request_refresh.assert_awaited_once()
        self.assertFalse(hasattr(self.coordinator, "async_set_updated_data"))

    async def test_subscribe_uses_unique_client_tls_and_never_publishes(self):
        client = types.SimpleNamespace(subscribe=AsyncMock(), publish=AsyncMock())
        async def messages():
            yield types.SimpleNamespace(topic=self.topic, payload=b'{"state":{}}', retain=False)
        client.messages = messages()
        manager = types.SimpleNamespace(__aenter__=AsyncMock(return_value=client), __aexit__=AsyncMock(return_value=False))
        class Manager:
            async def __aenter__(self): return await manager.__aenter__()
            async def __aexit__(self, *args): return await manager.__aexit__(*args)
        factory = Mock(return_value=Manager())
        self.live.client_factory = factory
        with self.assertRaises(ConnectionError): await self.live._connection("verified-tls-context")
        client.subscribe.assert_awaited_once_with(self.topic, qos=0)
        client.publish.assert_not_awaited()
        args = factory.call_args.kwargs
        self.assertEqual(args["tls_context"], "verified-tls-context")
        self.assertTrue(args["identifier"].startswith("ha-vestel-"))
        self.assertEqual(args["transport"], "websockets")
        self.assertTrue(self.live._pending.is_set())
        self.assertNotIn("TESTKEY", json.dumps(self.live.stats))
        self.assertNotIn("token", json.dumps(self.live.stats))

    async def test_network_timeout_backs_off_and_cancellation_cleans_up(self):
        self.live._connection = AsyncMock(side_effect=TimeoutError)
        with patch("custom_components.vestel_appliances.live.asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)) as sleep:
            with self.assertRaises(asyncio.CancelledError): await self.live.run()
        self.assertEqual(self.live.stats["failures"], 1)
        self.assertEqual(self.live.stats["last_error"], "TimeoutError")
        self.assertEqual(self.live.stats["state"], "stopped")
        self.assertGreaterEqual(sleep.await_args.args[0], 5)

    async def test_device_added_while_connected_restarts_subscription_session(self):
        first = asyncio.Event()
        second = asyncio.Event()
        sessions = []
        async def connection(tls_context):
            sessions.append(set(self.coordinator.data))
            (first if len(sessions) == 1 else second).set()
            await asyncio.Event().wait()
        self.live._connection = connection
        task = asyncio.create_task(self.live.run())
        try:
            await asyncio.wait_for(first.wait(), 2)
            self.coordinator.data["new-device"] = types.SimpleNamespace(metadata={})
            self.live._check_devices()
            await asyncio.wait_for(second.wait(), 2)
            self.assertEqual(sessions, [{"device"}, {"device", "new-device"}])
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.assertEqual(self.live.stats["state"], "stopped")

if __name__ == "__main__": unittest.main()
