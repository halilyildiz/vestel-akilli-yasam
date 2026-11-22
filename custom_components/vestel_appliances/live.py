"""Read-only AWS IoT subscriptions with polling fallback and coalesced refresh.

Credentials, signed URLs, topics, and payloads never enter diagnostics/logs.
No MQTT publish method is used. Appliance commands keep their REST transport.
"""
from __future__ import annotations
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import logging
import random
import ssl
import time
from uuid import uuid4
from .api import ApiError
from .mqtt_protocol import ENDPOINT, subscription_topics, websocket_path


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class SessionExpired(Exception):
    pass


class LiveUpdates:
    def __init__(self, hass, entry, coordinator, *, client_factory=None):
        self.hass, self.entry, self.coordinator = hass, entry, coordinator
        self.client_factory = client_factory
        self.task = None
        self._pending = asyncio.Event()
        self._topology_changed = asyncio.Event()
        self._device_ids = frozenset()
        self._identifier = "ha-vestel-" + uuid4().hex
        self.subscribed_devices = set()
        self.stats = {"state": "stopped", "subscription_count": 0, "messages_received": 0,
                      "refresh_count": 0, "failures": 0, "last_error": None,
                      "last_event_at": None, "last_refresh_at": None}
        self.stats["stage"] = "idle"

    @property
    def connected(self):
        return self.stats["state"] == "connected"

    def _state(self, state):
        self.stats["state"] = state
        if state != "connected":
            self.subscribed_devices.clear()
            self.stats["subscription_count"] = 0
        self.coordinator.async_update_listeners()

    def _check_devices(self):
        devices = frozenset(subscription_topics(self.coordinator.data or {}))
        if devices != self._device_ids:
            self._device_ids = devices
            self._topology_changed.set()

    def start(self):
        self._device_ids = frozenset(subscription_topics(self.coordinator.data or {}))
        self.entry.async_on_unload(self.coordinator.async_add_listener(self._check_devices))
        self.task = self.entry.async_create_background_task(self.hass, self.run(), "Vestel MQTT status")

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None

    def notify(self, topic, payload, retained, topics):
        # Retained messages may predate the initial REST snapshot. Even live
        # payloads only invalidate the cache: we never merge unverified bytes.
        if retained or topic not in topics or len(payload) > 262144:
            return
        self.stats["messages_received"] += 1
        self.stats["last_event_at"] = timestamp()
        self._pending.set()

    async def _refresh_worker(self):
        next_read = 0.0
        while True:
            await self._pending.wait()
            # Coalesce bursts and limit push-triggered reads to one per 10 s.
            await asyncio.sleep(max(1.0, next_read - time.monotonic()))
            self._pending.clear()
            try:
                await self.coordinator.async_request_refresh()
                self.stats["refresh_count"] += 1
                self.stats["last_refresh_at"] = timestamp()
            except Exception:
                # Polling remains responsible for surfacing REST failures.
                self.stats["last_error"] = "status_refresh_failed"
            next_read = time.monotonic() + 10

    async def _connection(self, tls_context):
        topics = subscription_topics(self.coordinator.data or {})
        if not topics:
            raise ApiError("Canlı veri için cihaz kanalı bulunamadı.")
        self.stats["stage"] = "credentials"
        credentials = await self.coordinator.api.iot_credentials()
        if self.client_factory is None:
            from aiomqtt import Client, ProtocolVersion
            factory = Client
            protocol = ProtocolVersion.V311
        else:
            factory = self.client_factory
            protocol = None
        # Isolate library transport logs; a failed handshake may include its
        # signed URL. Only the safe error class is exposed by this component.
        transport_logger = logging.getLogger("vestel_appliances.mqtt_transport")
        transport_logger.propagate = False
        transport_logger.addHandler(logging.NullHandler()) if not transport_logger.handlers else None
        self.stats["stage"] = "connect"
        async with factory(ENDPOINT, port=443, identifier=self._identifier,
            transport="websockets", protocol=protocol, clean_session=True,
            tls_context=tls_context, websocket_path=websocket_path(credentials),
            timeout=20, keepalive=30, max_queued_incoming_messages=100,
            logger=transport_logger) as client:
            # Reconnect with fresh credentials before expiration. Expiry of a
            # signed connection URL does not by itself expire an open socket.
            lifetime = max(1, min(2700, credentials["expiration"] - time.time() - 120))
            deadline = asyncio.timeout(lifetime)
            try:
                async with deadline:
                    self.stats["stage"] = "subscribe"
                    for topic, uuids in topics.items():
                        await client.subscribe(topic, qos=0)
                        self.subscribed_devices.update(uuids)
                    self.stats["subscription_count"] = len(topics)
                    self.stats["last_error"] = None
                    self._state("connected")
                    self.stats["stage"] = "stream"
                    async for message in client.messages:
                        self.notify(str(message.topic), message.payload, message.retain, topics)
            except TimeoutError:
                if deadline.expired():
                    raise SessionExpired from None
                raise
        raise ConnectionError("stream_closed")

    async def run(self):
        worker = asyncio.create_task(self._refresh_worker())
        delay = 5
        try:
            tls_context = await self.hass.async_add_executor_job(ssl.create_default_context)
            while True:
                self._state("connecting")
                connected_at = time.monotonic()
                try:
                    self._topology_changed.clear()
                    connection = asyncio.create_task(self._connection(tls_context))
                    topology = asyncio.create_task(self._topology_changed.wait())
                    try:
                        done, _ = await asyncio.wait((connection, topology), return_when=asyncio.FIRST_COMPLETED)
                        if topology in done:
                            raise SessionExpired
                        await connection
                    finally:
                        for task in (connection, topology):
                            task.cancel()
                        for task in (connection, topology):
                            with suppress(asyncio.CancelledError, Exception):
                                await task
                except asyncio.CancelledError:
                    raise
                except SessionExpired:
                    # The bounded session expired normally; renew immediately.
                    self._state("reconnecting")
                    delay = 5
                    continue
                except Exception as err:
                    self.stats["failures"] += 1
                    self.stats["last_error"] = type(err).__name__
                    self._state("retrying")
                    if time.monotonic() - connected_at > 60:
                        delay = 5
                    await asyncio.sleep(delay + random.uniform(0, 1))
                    delay = min(delay * 2, 300)
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            self._state("stopped")
