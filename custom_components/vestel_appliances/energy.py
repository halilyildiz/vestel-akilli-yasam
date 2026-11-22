"""Slow, isolated energy history polling; appliance control never depends on it."""
from __future__ import annotations
import asyncio
import logging
import math
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .api import ApiError


def sample_value(history, metric):
    """Return missing as unknown, preserving a genuine server zero."""
    samples = (history or {}).get("samples") or []
    if not samples:
        return None
    value = samples[0].get("consumption", {}).get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


class EnergyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, appliances):
        super().__init__(hass, logging.getLogger(__name__), name="vestel_appliances_energy",
                         config_entry=entry, update_interval=timedelta(hours=1))
        self.appliances = appliances
        self.api = appliances.api
        self.entry = entry
        self.billing = None

    async def async_refresh_billing(self):
        try:
            self.billing = await self.api.billing_settings(self.entry.data["home_id"])
        except ApiError:
            self.billing = None
        self.async_update_listeners()

    async def _async_update_data(self):
        home = self.entry.data["home_id"]
        # Bound concurrency: two devices at once, two sequential reads/device.
        limit = asyncio.Semaphore(2)
        async def read(uuid):
            result = {}
            async with limit:
                for period in ("day", "month"):
                    try:
                        result[period] = await self.api.consumption(home, uuid, period, 1)
                    except ApiError:
                        result[period] = None
            return uuid, result
        pairs = await asyncio.gather(*(read(uuid) for uuid in (self.appliances.data or {})))
        try:
            self.billing = await self.api.billing_settings(home)
        except ApiError:
            self.billing = None
        return dict(pairs)
