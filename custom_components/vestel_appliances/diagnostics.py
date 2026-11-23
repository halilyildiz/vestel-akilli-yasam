from .const import DOMAIN
from .redaction import metadata_view, sanitize, _private_values


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = coordinator.data or {}
    payload = {
        "compatibility": {
            "device_collections": getattr(coordinator.api, "inventory_summary", {}),
            "unsupported_types": coordinator.unsupported_types,
            "incompatible_devices": coordinator.compatibility_errors,
            "platform_errors": sorted(coordinator.platform_errors),
        },
        "live_updates": dict(coordinator.live.stats),
        "devices": [{
            "metadata": metadata_view(state.metadata),
            "support_level": state.support_level,
            "discovery": state.discovery,
            "registers": state.registers,
            "read_ok": state.read_ok,
            "last_command": coordinator.last_commands.get(uuid),
        } for uuid, state in devices.items()],
    }
    # Gather before filtering so identifiers repeated in discovery/notes are
    # still removed. Account credentials are used only for redaction.
    private = _private_values(
        [entry.data, payload, *(state.metadata for state in devices.values()),
         {"deviceId": list(devices)}], entry.data["home_id"])
    return sanitize(payload, private)
