from __future__ import annotations
import asyncio
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import logging
import re

from .errors import user_error
from .api import ApiError, AuthError
from .const import DOMAIN, SCAN_SECONDS, SUPPORTED_TYPES
from .fields import SchemaError
from .protocol import Device
from .discovery import prepare_discovery
from .issues import update_issues


class Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, api):
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         config_entry=entry, update_interval=timedelta(seconds=SCAN_SECONDS))
        self.api, self.entry = api, entry
        self.schemas = {}
        self.locks = {}
        self.last_commands = {}
        self.pending = {}
        self._hass = hass
        self.schema_versions = {}
        self.unsupported_types = {}
        self.compatibility_errors = {}
        self.platform_errors = set()

    async def _async_update_data(self):
        try:
            devices = await self.api.devices(self.entry.data["home_id"])
        except AuthError as err:
            raise user_error(err, error_type=ConfigEntryAuthFailed) from None
        except ApiError as err:
            raise user_error(err, error_type=UpdateFailed) from None
        result = {}
        unsupported = {}
        incompatible = {}
        for item in devices:
            if not isinstance(item, dict):
                incompatible["invalid_metadata"] = "invalid_metadata"
                continue
            family = item.get("deviceType")
            if not isinstance(family, str) or family not in SUPPORTED_TYPES:
                label = family if isinstance(family, str) and re.fullmatch(r"[A-Za-z0-9_]{1,24}", family) else "UNKNOWN"
                unsupported[label] = unsupported.get(label, 0) + 1
                continue
            uuid = item.get("deviceId")
            if not isinstance(uuid, str) or not uuid:
                incompatible["missing_device_id"] = "missing_device_id"
                continue
            revision = tuple(str(item.get(k, "")) for k in
                             ("deviceType", "variant", "deviceModel", "wifiVersion", "wifiCardType"))
            try:
                if not isinstance(item.get("wifiCardType"), str) or not item["wifiCardType"]:
                    raise SchemaError("missing_transport_type")
                if uuid not in self.schemas or self.schema_versions.get(uuid, revision) != revision:
                    schema = prepare_discovery(await self.api.discovery(uuid), family)
                    self.schemas[uuid] = schema
                    self.schema_versions[uuid] = revision
                registers = await self.api.status(uuid) if item.get("connected", True) else {}
                if not isinstance(registers, dict):
                    raise SchemaError("invalid_status")
                result[uuid] = Device(item, self.schemas[uuid], registers, bool(registers))
                expected = self.pending.get(uuid)
                cancelling = self.last_commands.get(uuid, {}).get("operation") == "cancelling"
                stopped = str(registers.get("DWPROST")) in {"0", "00000", "3", "00003"}
                if expected and (not cancelling or stopped) and expected.matches(registers):
                    self.last_commands[uuid].update(readback_confirmed=True, operation="confirmed")
                    self.pending.pop(uuid, None)
            except AuthError as err:
                raise user_error(err, error_type=ConfigEntryAuthFailed) from None
            except ApiError:
                # Transient cloud failure is not proof that a model is unsupported.
                result[uuid] = Device(item, self.schemas.get(uuid, {}), {}, False)
            except (SchemaError, KeyError, TypeError, ValueError, AttributeError) as err:
                incompatible[uuid] = type(err).__name__
                result[uuid] = Device(item, {}, {}, False)
        self.platform_errors = {key for key in self.platform_errors if key[1] in result}
        for uuid in set(self.schemas) - set(result):
            self.schemas.pop(uuid, None)
            self.schema_versions.pop(uuid, None)
        self.unsupported_types = unsupported
        self.compatibility_errors = incompatible
        if self._hass is not None:
            update_issues(self._hass, self.entry, unsupported, len(incompatible) + len(self.platform_errors))
        # An empty/unsupported-only account must stay loaded so future devices
        # can be discovered and compatibility notices remain visible.
        return result

    def set_platform_error(self, uuid: str, platform: str, failed: bool) -> None:
        key = (platform, uuid)
        if failed:
            self.platform_errors.add(key)
        else:
            self.platform_errors.discard(key)
        if self._hass is not None:
            update_issues(self._hass, self.entry, self.unsupported_types,
                          len(self.compatibility_errors) + len(self.platform_errors))

    async def apply(self, uuid, *, updates=None, command=None):
        """Serialize each appliance's writes and re-read before bit merging.

        Transport acceptance and readback are separate; no optimistic state.
        A missing acknowledgement never causes a command to be replayed.
        """
        async with self.locks.setdefault(uuid, asyncio.Lock()):
            state = (self.data or {}).get(uuid)
            if state is None:
                raise user_error('device_not_found')
            if not state.writable:
                raise user_error('monitoring_only')
            try:
                items = await self.api.devices(self.entry.data["home_id"])
                metadata = next((d for d in items if d.get("deviceId") == uuid), None)
                if metadata is None or metadata.get("connected") is False:
                    raise SchemaError('device_offline')
                fresh = Device(metadata, state.discovery, await self.api.status(uuid))
                if not fresh.registers:
                    raise SchemaError('empty_status')
                if command and fresh.family == "DW" and command.endswith(".Command.Cancel") and str(fresh.registers.get("DWWARNS")) in {"1", "00001"}:
                    raise SchemaError('cancel_in_progress')
                codes = [fresh.command(command)] if command else fresh.build(updates or [])
                if not codes:
                    raise SchemaError('no_changes')
                expected = fresh.expected_readback(codes, updates=updates, command=command)
                cancelling = bool(command and fresh.family == "DW" and command.endswith(".Command.Cancel"))
                for code in codes:
                    await self.api.send(metadata, code)
                self.last_commands[uuid] = {"accepted": True, "readback_confirmed": False}
                if cancelling:
                    self.last_commands[uuid]["operation"] = "cancelling"
                # Some appliances report writes well after six seconds. Never
                # resend an accepted command merely because the echo is late.
                self.pending[uuid] = expected
                for attempt in range(6):
                    await asyncio.sleep(2 if attempt < 2 else 5)
                    fresh.registers = await self.api.status(uuid)
                    if cancelling and str(fresh.registers.get("DWWARNS")) in {"1", "00001"}:
                        self.last_commands[uuid]["operation"] = "cancelling"
                        self.async_set_updated_data({**self.data, uuid: fresh})
                        return {"accepted": True, "readback_confirmed": False, "operation": "cancelling"}
                    stopped = str(fresh.registers.get("DWPROST")) in {"0", "00000", "3", "00003"}
                    if (not cancelling or stopped) and expected.matches(fresh.registers):
                        self.last_commands[uuid]["readback_confirmed"] = True
                        self.last_commands[uuid]["operation"] = "confirmed"
                        self.pending.pop(uuid, None)
                        self.async_set_updated_data({**self.data, uuid: fresh})
                        return {"accepted": True, "readback_confirmed": True}
                    self.async_set_updated_data({**self.data, uuid: fresh})
                raise user_error('command_unconfirmed')
            except (ApiError, SchemaError) as err:
                raise user_error(err) from None
