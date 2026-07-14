"""Environment state models for basement / enclosure / ambient extremes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EnclosureMode(str, Enum):
    OPEN = "open"  # no enclosure
    ENCLOSED = "enclosed"
    DOOR_AJAR = "door_ajar"  # partial / vented enclosure


class Phase(str, Enum):
    BEFORE = "before"  # preflight + heat + soak
    DURING = "during"  # active print
    AFTER = "after"  # cool-down / part release / stress relief


class EnvironmentBin(str, Enum):
    """Coarse bins for learned homeostasis memory."""

    COLD_DRY = "cold_dry"
    COLD_HUMID = "cold_humid"
    MILD = "mild"
    WARM_DRY = "warm_dry"
    WARM_HUMID = "warm_humid"
    HOT = "hot"


@dataclass
class AmbientReading:
    """Shop air around the printer (manual, IoT, or estimated)."""

    temperature_c: float
    rh_percent: float
    enclosure: EnclosureMode = EnclosureMode.OPEN
    # Optional extras
    chamber_temperature_c: Optional[float] = None  # if sensor or estimate
    draft_level: float = 0.0  # 0..1 subjective or anemometer later
    source: str = "manual"  # manual | sensor | estimate
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "rh_percent": self.rh_percent,
            "enclosure": self.enclosure.value,
            "chamber_temperature_c": self.chamber_temperature_c,
            "draft_level": self.draft_level,
            "source": self.source,
            "notes": self.notes,
        }

    def environment_bin(self) -> EnvironmentBin:
        t = float(self.temperature_c)
        rh = float(self.rh_percent)
        humid = rh >= 55.0
        dry = rh < 40.0
        if t < 16.0:
            return EnvironmentBin.COLD_HUMID if humid else EnvironmentBin.COLD_DRY
        if t >= 30.0:
            return EnvironmentBin.HOT
        if t >= 24.0:
            return EnvironmentBin.WARM_HUMID if humid else EnvironmentBin.WARM_DRY
        if 18.0 <= t < 24.0 and 35.0 <= rh <= 55.0:
            return EnvironmentBin.MILD
        if humid:
            return EnvironmentBin.WARM_HUMID if t >= 20.0 else EnvironmentBin.COLD_HUMID
        if dry and t >= 20.0:
            return EnvironmentBin.WARM_DRY
        return EnvironmentBin.MILD


# Ideal "lab" reference for deltas (not a claim the basement is this)
REFERENCE_TEMP_C = 22.0
REFERENCE_RH = 40.0


@dataclass
class EnvironmentProfile:
    """Named shop profile (e.g. basement_winter)."""

    name: str
    ambient: AmbientReading
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "ambient": self.ambient.as_dict(),
            "bin": self.ambient.environment_bin().value,
        }


def basement_default_profile(
    temperature_c: float = 14.0,
    rh_percent: float = 65.0,
    enclosure: EnclosureMode = EnclosureMode.OPEN,
) -> EnvironmentProfile:
    """Typical unfinished/finished basement: cool + elevated RH."""
    return EnvironmentProfile(
        name="basement_default",
        description="Cool humid basement shop; long soaks, adhesion-first first layer",
        tags=["basement", "cold", "humid"],
        ambient=AmbientReading(
            temperature_c=temperature_c,
            rh_percent=rh_percent,
            enclosure=enclosure,
            draft_level=0.25 if enclosure == EnclosureMode.OPEN else 0.05,
            source="profile",
            notes="Edit via FORGE_SET_AMBIENT or env YAML",
        ),
    )
