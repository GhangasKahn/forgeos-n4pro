"""Versioned material packs (Protopasta HTPLA / HTPLA-CF)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


class MaterialError(Exception):
    pass


@dataclass(frozen=True)
class AnnealSpec:
    temp_c: float
    hold_min: float
    cool_rate: str
    xy_scale: float
    z_scale: float
    hole_extra_mm: float


@dataclass(frozen=True)
class MaterialPack:
    sku: str
    name: str
    family: str
    version: int
    abrasive: bool
    nozzle_required_type: str
    nozzle_min_diameter_mm: float
    nozzle_preferred_diameter_mm: float
    density_g_cm3: float
    nozzle_temp_range_c: List[float]
    nozzle_default_c: float
    bed_temp_range_c: List[float]
    bed_default_c: float
    max_volumetric_flow_mm3_s: float
    pressure_advance_seed: float
    flow_multiplier_seed: float
    role_speeds_mm_s: Dict[str, float]
    role_accel_mm_s2: Dict[str, float]
    anneal: AnnealSpec
    part_class_defaults: Dict[str, str]
    notes: List[str]
    raw: Dict[str, Any]

    def recipe_for_part_class(self, part_class: str) -> str:
        return self.part_class_defaults.get(part_class, "balanced")


def _require(d: Dict[str, Any], key: str) -> Any:
    if key not in d:
        raise MaterialError("missing key: %s" % key)
    return d[key]


def load_material_pack(path: Path) -> MaterialPack:
    path = Path(path)
    if not path.is_file():
        raise MaterialError("material pack not found: %s" % path)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise MaterialError("material pack must be a mapping")

    nozzle = _require(data, "nozzle")
    temps = _require(data, "temps")
    anneal_raw = _require(data, "anneal")

    n_range = list(temps["nozzle_c"])
    b_range = list(temps["bed_c"])
    if len(n_range) != 2 or n_range[0] >= n_range[1]:
        raise MaterialError("temps.nozzle_c must be [lo, hi]")
    if len(b_range) != 2 or b_range[0] >= b_range[1]:
        raise MaterialError("temps.bed_c must be [lo, hi]")

    flow = float(data["max_volumetric_flow_mm3_s"])
    if flow <= 0:
        raise MaterialError("max_volumetric_flow_mm3_s must be > 0")

    anneal = AnnealSpec(
        temp_c=float(anneal_raw["temp_c"]),
        hold_min=float(anneal_raw["hold_min"]),
        cool_rate=str(anneal_raw.get("cool_rate", "oven_off_natural")),
        xy_scale=float(anneal_raw["xy_scale"]),
        z_scale=float(anneal_raw["z_scale"]),
        hole_extra_mm=float(anneal_raw.get("hole_extra_mm", 0.0)),
    )
    if anneal.xy_scale <= 0 or anneal.z_scale <= 0:
        raise MaterialError("anneal scales must be positive")

    return MaterialPack(
        sku=str(_require(data, "sku")),
        name=str(data.get("name", data["sku"])),
        family=str(data.get("family", "unknown")),
        version=int(data.get("version", 1)),
        abrasive=bool(data.get("abrasive", False)),
        nozzle_required_type=str(nozzle.get("required_type", "hardened")),
        nozzle_min_diameter_mm=float(nozzle.get("min_diameter_mm", 0.4)),
        nozzle_preferred_diameter_mm=float(nozzle.get("preferred_diameter_mm", 0.4)),
        density_g_cm3=float(data.get("density_g_cm3", 1.24)),
        nozzle_temp_range_c=[float(n_range[0]), float(n_range[1])],
        nozzle_default_c=float(temps.get("nozzle_default_c", sum(n_range) / 2.0)),
        bed_temp_range_c=[float(b_range[0]), float(b_range[1])],
        bed_default_c=float(temps.get("bed_default_c", sum(b_range) / 2.0)),
        max_volumetric_flow_mm3_s=flow,
        pressure_advance_seed=float(data.get("pressure_advance_seed", 0.03)),
        flow_multiplier_seed=float(data.get("flow_multiplier_seed", 1.0)),
        role_speeds_mm_s={k: float(v) for k, v in dict(data.get("role_speeds_mm_s", {})).items()},
        role_accel_mm_s2={k: float(v) for k, v in dict(data.get("role_accel_mm_s2", {})).items()},
        anneal=anneal,
        part_class_defaults={k: str(v) for k, v in dict(data.get("part_class_defaults", {})).items()},
        notes=[str(x) for x in list(data.get("notes", []))],
        raw=data,
    )


def load_all_packs(materials_dir: Path) -> Dict[str, MaterialPack]:
    materials_dir = Path(materials_dir)
    packs: Dict[str, MaterialPack] = {}
    for path in sorted(materials_dir.glob("*.yaml")):
        pack = load_material_pack(path)
        if pack.sku in packs:
            raise MaterialError("duplicate sku: %s" % pack.sku)
        packs[pack.sku] = pack
    return packs


def default_materials_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "materials"
