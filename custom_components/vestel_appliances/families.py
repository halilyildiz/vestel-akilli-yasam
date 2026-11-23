"""Explicit protocol coverage; a shared app does not imply a shared transport."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

SupportLevel = Literal["controls", "experimental_controls", "monitoring"]


@dataclass(frozen=True, slots=True)
class FamilyProfile:
    """Evidence-based coverage for a legacy-register appliance family."""

    name: str
    support_level: SupportLevel

    @property
    def writable(self) -> bool:
        return self.support_level != "monitoring"


FAMILY_PROFILES: Final[Mapping[str, FamilyProfile]] = MappingProxyType({
    "AC": FamilyProfile("Air conditioner", "controls"),
    "WD": FamilyProfile("Washer-dryer", "controls"),
    "DW": FamilyProfile("Dishwasher", "controls"),
    "RF": FamilyProfile("Refrigerator", "controls"),
    "WM": FamilyProfile("Washing machine", "experimental_controls"),
    "FD": FamilyProfile("French-door refrigerator", "experimental_controls"),
    "TD": FamilyProfile("Tumble dryer", "monitoring"),
    "OV": FamilyProfile("Oven", "monitoring"),
})
