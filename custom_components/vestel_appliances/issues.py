"""Account-scoped compatibility notices using Home Assistant Repairs."""
from __future__ import annotations

from typing import Any
from .const import DOMAIN


def update_issues(hass: Any, entry: Any, unsupported: dict[str, int], incompatible: int) -> None:
    from homeassistant.helpers import issue_registry as ir

    for key, placeholders, active in (
        ("unsupported_devices", {"device_types": ", ".join(sorted(unsupported)),
                                 "count": str(sum(unsupported.values()))}, bool(unsupported)),
        ("incompatible_devices", {"count": str(incompatible)}, bool(incompatible)),
    ):
        issue_id = f"{key}_{entry.entry_id}"
        if active:
            ir.async_create_issue(hass, DOMAIN, issue_id, config_entry_id=entry.entry_id,
                                  is_fixable=False, severity=ir.IssueSeverity.WARNING,
                                  translation_key=key, translation_placeholders=placeholders)
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
