"""Read-only collection using the already authenticated Vestel client.

This module deliberately has no Home Assistant dependency or command method.
Only the three documented read methods below are accepted.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Protocol

from .errors import LocalizedError


class ReadClient(Protocol):
    async def async_get_devices(self, home_id: str) -> list[dict]: ...
    async def async_get_discovery(self, uuid: str) -> dict: ...
    async def async_get_status(self, uuid: str) -> dict: ...


class CollectionError(LocalizedError):
    """A deliberately detail-free error safe to show in HA."""


PRIVATE_KEY = re.compile(
    r"token|secret|password|email|phone|mac|serial|ssid|topic|username|"
    r"deviceid|devicename|homeid|homename|roomid|roomname|registeredby|"
    r"ordernumber|customerid|identityid|authorization|address|latitude|longitude|"
    r"accesskey|apikey|cookie|credential",
    re.I,
)
IDENTIFIER = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|(?:[0-9a-f]{2}:){5}[0-9a-f]{2}"
    r"|[A-Z]{2,3}_[A-Z_]*[0-9a-f]{16,}"
    r"|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    re.I,
)
METADATA = (
    "deviceType", "deviceModel", "variant", "wifiCardType", "wifiVersion",
    "oemBrand", "connected", "isActive", "isSmart",
)


def metadata_view(metadata: dict) -> dict:
    """Export only known technical fields, never arbitrary nested cloud data."""
    return {key: metadata[key] for key in METADATA
            if key in metadata and type(metadata[key]) in (str, int, float, bool)}


def sanitize(value: Any, private_values: tuple[str, ...] = ()) -> Any:
    """Redact identifier fields and identifiers embedded in strings/JSON."""
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            safe_key = sanitize(str(key), private_values)
            compact = re.sub(r"[^a-z0-9]", "", str(key).lower())
            result[safe_key] = (
                "[REDACTED]" if PRIVATE_KEY.search(compact)
                else sanitize(child, private_values)
            )
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize(child, private_values) for child in value]
    if isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                return json.dumps(sanitize(json.loads(value), private_values), ensure_ascii=False)
            except (ValueError, RecursionError):
                pass
        for private in sorted(private_values, key=len, reverse=True):
            if private:
                value = value.replace(private, "[REDACTED]")
        return IDENTIFIER.sub("[REDACTED]", value)
    return value


def _private_values(devices: list[dict], home_id: str) -> tuple[str, ...]:
    values = {home_id}

    def visit(value, private=False):
        if isinstance(value, dict):
            for key, child in value.items():
                compact = re.sub(r"[^a-z0-9]", "", str(key).lower())
                visit(child, private or bool(PRIVATE_KEY.search(compact)))
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child, private)
        elif isinstance(value, str):
            if private and len(value) >= 4:
                values.add(value)
            if value.lstrip().startswith(("{", "[")):
                try:
                    visit(json.loads(value), private)
                except (ValueError, RecursionError):
                    pass

    for device in devices:
        visit(device)
    return tuple(values)


def summarize(discovery: dict) -> dict:
    """Keep full definitions separately; return concise counts for triage."""
    groups = ("settings", "options", "programs", "commands", "status", "errors")
    blocks = [discovery, *(discovery.get("components") or [])]
    return {
        group: sum(len(block.get(group) or []) for block in blocks if isinstance(block, dict))
        for group in groups
    }


async def collect(api: ReadClient, home_id: str) -> dict:
    """Collect a single snapshot; an unsupported/offline appliance is isolated."""
    try:
        devices = await asyncio.wait_for(api.async_get_devices(home_id), timeout=45)
    except Exception:
        raise CollectionError('collection_failed') from None
    if not isinstance(devices, list) or any(not isinstance(d, dict) for d in devices):
        raise CollectionError('collection_invalid')

    private = _private_values(devices, home_id)
    results = []
    for index, device in enumerate(devices, 1):
        record = {
            "alias": f"device_{index}",
            "metadata": metadata_view(device),
            "discovery": None,
            "registers": None,
            "errors": {},
        }
        uuid = device.get("deviceId")
        if not isinstance(uuid, str) or not uuid:
            record["errors"]["device"] = "missing_device_id"
            results.append(record)
            continue
        # Do not skip offline devices: the cloud may have cached metadata/status.
        for key, method in (("discovery", api.async_get_discovery), ("registers", api.async_get_status)):
            try:
                payload = await asyncio.wait_for(method(uuid), timeout=45)
                if not isinstance(payload, dict):
                    record["errors"][key] = "unexpected_response_shape"
                else:
                    record[key] = payload
            except Exception:
                # Exception messages can contain URLs, account IDs or tokens.
                record["errors"][key] = "read_failed"
        if record["discovery"] is not None:
            record["capability_counts"] = summarize(record["discovery"])
        results.append(record)

    return sanitize({
        "schema_version": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "vestel_smarthome authenticated read methods",
        "read_only": True,
        "device_count": len(results),
        "devices": results,
        "notes": [
            "Snapshot only; cloud status can be stale.",
            "No appliance command or MQTT policy change was performed.",
            "Model codes and discovery definitions are retained; account/device identifiers are redacted.",
        ],
    }, private)
