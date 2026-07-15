"""Load and validate the canonical Neptune 4 Pro machine profile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union

import yaml


class ProfileError(ValueError):
    """Raised when a machine profile is incomplete or unsafe."""


def default_profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "neptune4pro.yaml"


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError("%s must be numeric" % path)
    return float(value)


def _mapping(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileError("%s must be a mapping" % path)
    return value


def _require(data: Dict[str, Any], keys: Iterable[str], path: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ProfileError("%s missing: %s" % (path, ", ".join(missing)))


@dataclass(frozen=True)
class MachineProfile:
    path: Path
    raw: Dict[str, Any]

    @property
    def model(self) -> str:
        return str(self.raw["machine"]["model"])

    @property
    def motion(self) -> Dict[str, Any]:
        return self.raw["motion"]

    @property
    def acceptance(self) -> Dict[str, float]:
        return {key: float(value) for key, value in self.raw["acceptance"].items()}

    @property
    def probe(self) -> Dict[str, Any]:
        return self.raw["probe"]

    @property
    def network(self) -> Dict[str, Any]:
        return self.raw["network"]


def load_machine_profile(path: Optional[Union[Path, str]] = None) -> MachineProfile:
    profile_path = Path(path) if path is not None else default_profile_path()
    if not profile_path.is_file():
        raise ProfileError("machine profile not found: %s" % profile_path)
    with profile_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    data = _mapping(raw, "profile")
    _require(
        data,
        ("schema_version", "machine", "network", "motion", "thermal", "probe", "safety", "acceptance"),
        "profile",
    )
    machine = _mapping(data["machine"], "machine")
    _require(machine, ("model", "firmware_family", "build_volume_mm"), "machine")
    volume = machine["build_volume_mm"]
    if not isinstance(volume, list) or len(volume) != 3 or any(_number(v, "build_volume_mm") <= 0 for v in volume):
        raise ProfileError("machine.build_volume_mm must contain three positive numbers")

    motion = _mapping(data["motion"], "motion")
    _require(
        motion,
        ("max_velocity_mm_s", "max_accel_mm_s2", "max_z_velocity_mm_s", "max_z_accel_mm_s2"),
        "motion",
    )
    for key in ("max_velocity_mm_s", "max_accel_mm_s2", "max_z_velocity_mm_s", "max_z_accel_mm_s2"):
        if _number(motion[key], "motion.%s" % key) <= 0:
            raise ProfileError("motion.%s must be positive" % key)
    if _number(motion["max_velocity_mm_s"], "motion.max_velocity_mm_s") > 500:
        raise ProfileError("motion velocity exceeds Neptune 4 Pro safety ceiling")
    if _number(motion["max_accel_mm_s2"], "motion.max_accel_mm_s2") > 10000:
        raise ProfileError("motion acceleration exceeds Neptune 4 Pro safety ceiling")

    probe = _mapping(data["probe"], "probe")
    _require(probe, ("offset_xy_mm", "repeatability_range_max_mm", "mesh_bounds_mm"), "probe")
    if len(probe["offset_xy_mm"]) != 2 or len(probe["mesh_bounds_mm"]) != 4:
        raise ProfileError("probe offsets/bounds have invalid dimensions")

    acceptance = _mapping(data["acceptance"], "acceptance")
    _require(
        acceptance,
        (
            "heater_stability_c",
            "bed_mesh_range_fail_mm",
            "dimensional_error_100mm_max_mm",
            "repeatability_span_3x_max_mm",
        ),
        "acceptance",
    )
    for key, value in acceptance.items():
        if _number(value, "acceptance.%s" % key) <= 0:
            raise ProfileError("acceptance.%s must be positive" % key)
    return MachineProfile(path=profile_path, raw=data)
