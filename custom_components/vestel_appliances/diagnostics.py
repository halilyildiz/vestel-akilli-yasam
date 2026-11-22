from .const import DOMAIN
from .redaction import sanitize, _private_values


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = list((coordinator.data or {}).values())
    private = _private_values([s.metadata for s in devices], entry.data["home_id"])
    return sanitize({"compatibility": {"unsupported_types": coordinator.unsupported_types,
        "incompatible_devices": coordinator.compatibility_errors,
        "platform_errors": sorted(coordinator.platform_errors)}, "live_updates": dict(coordinator.live.stats), "devices": [{"metadata": s.metadata, "discovery": s.discovery,
        "registers": s.registers, "read_ok": s.read_ok,
        "last_command": coordinator.last_commands.get(uuid)}
        for uuid, s in (coordinator.data or {}).items()]}, private)
