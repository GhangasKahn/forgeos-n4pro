"""Compose process profile: Protopasta filament + Wham Bam PEX + Brozzl nozzle."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from forgeos.materials import MaterialPack, load_material_pack, default_materials_dir


class StackError(Exception):
    pass


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise StackError("invalid yaml: %s" % path)
    return data


def hardware_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "materials" / "hardware"


@dataclass
class StackProfile:
    """Resolved settings for one print stack."""

    filament_sku: str
    surface_sku: str
    nozzle_sku: str
    nozzle_diameter_mm: float
    nozzle_type_token: str  # for FORGE_SET_NOZZLE
    abrasive: bool
    bed_c: float
    nozzle_c: float
    soak_min: float
    first_layer_height_mm: float
    first_layer_speed_mm_s: float
    first_layer_flow: float
    line_width_mm: float
    retract_mm: float
    retract_speed_mm_s: float
    unretract_speed_mm_s: float
    wipe_mm: float
    wipe_speed_mm_s: float
    z_hop_mm: float
    outer_wall_speed_mm_s: float
    travel_speed_mm_s: float
    pressure_advance: float
    pressure_advance_smooth_time: float
    max_volumetric_flow_mm3_s: float
    fan_layer_start: int
    brim: bool
    glue: bool
    z_adjust_seed: float
    notes: tuple

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def gcode_env_commands(self) -> list:
        return [
            'FORGE_SET_SURFACE TYPE=pex NAME="WhamBam PEX"',
            "FORGE_SET_NOZZLE TYPE=%s DIA=%.2f" % (self.nozzle_type_token, self.nozzle_diameter_mm),
            "FORGE_SET_MATERIAL SKU=%s" % self.filament_sku,
            "FORGE_SET_Z_ADJUST Z=%.3f" % self.z_adjust_seed,
            "FORGE_APPLY_ENV_TARGETS BED=%.1f NOZ=%.1f SOAK=%.2f"
            % (self.bed_c, self.nozzle_c, self.soak_min),
            "FORGE_SET_RETRACT LENGTH=%.2f SPEED=%.0f WIPE=%.2f ZHOP=%.2f"
            % (self.retract_mm, self.retract_speed_mm_s, self.wipe_mm, self.z_hop_mm),
            "FORGE_SET_PA PA=%.4f SMOOTH=%.3f"
            % (self.pressure_advance, self.pressure_advance_smooth_time),
            "FORGE_PREFLIGHT",
        ]


def compose_stack(
    filament_sku: str = "protopasta_htpla",
    surface_sku: str = "whambam_pex",
    nozzle_sku: str = "brozzl_nickel_copper_n4pro",
    ambient_temp_c: float = 14.0,
    materials_dir: Optional[Path] = None,
    z_adjust_seed: float = 0.05,
) -> StackProfile:
    mdir = materials_dir or default_materials_dir()
    pack = load_material_pack(mdir / ("%s.yaml" % filament_sku))
    surf_path = hardware_dir() / ("%s.yaml" % surface_sku)
    if not surf_path.is_file():
        surf_path = hardware_dir() / "whambam_pex.yaml"
    surf = _load_yaml(surf_path)

    noz_path = hardware_dir() / ("%s.yaml" % nozzle_sku)
    if not noz_path.is_file():
        # aliases
        aliases = {
            "brozzl": "brozzl_n4pro.yaml",
            "brozzl_ni_cu": "brozzl_n4pro.yaml",
            "brozzl_nickel_copper_n4pro": "brozzl_n4pro.yaml",
            "brozzl_plated_copper": "brozzl_n4pro.yaml",
            "brozzl_plated_copper_0.4": "brozzl_n4pro.yaml",
            "plated_copper": "brozzl_n4pro.yaml",
        }
        noz_path = hardware_dir() / aliases.get(nozzle_sku, "brozzl_n4pro.yaml")
    noz = _load_yaml(noz_path)

    if pack.abrasive and not noz.get("abrasive_rated", False):
        raise StackError(
            "Abrasive filament %s requires hardened nozzle; %s is soft Ni-Cu/brass class"
            % (filament_sku, nozzle_sku)
        )

    fl = dict(pack.raw.get("first_layer") or {})
    ret = dict(pack.raw.get("retract") or {})
    surf_bias = dict(surf.get("process_bias") or {})
    noz_bias = dict(noz.get("process_bias") or {})

    bed = float(fl.get("bed_c", pack.bed_default_c))
    # surface preferred bed for htpla
    if "htpla" in pack.family:
        bed = float(surf.get("temps_c", {}).get("htpla_bed", bed))
    bed = max(pack.bed_temp_range_c[0], min(pack.bed_temp_range_c[1], bed))

    noz_c = float(fl.get("nozzle_c", pack.nozzle_default_c))
    # stringing bias + plated-copper conductivity offset (copper runs "hotter" at same set-point)
    string_bias = float((pack.raw.get("stringing_control") or {}).get("nozzle_bias_c", 0))
    noz_c = noz_c + string_bias + float(noz_bias.get("nozzle_temp_offset_c", 0))
    noz_c = max(pack.nozzle_temp_range_c[0], min(pack.nozzle_temp_range_c[1], noz_c))

    soak = 3.0
    if ambient_temp_c < 18.0:
        soak += float(surf_bias.get("bed_soak_extra_min_cold", 2.0))
        soak += (18.0 - ambient_temp_c) * 0.25
    soak = max(3.0, min(12.0, soak))

    sc = dict(pack.raw.get("stringing_control") or {})
    pa = float(sc.get("pressure_advance", pack.pressure_advance_seed)) * float(
        noz_bias.get("pressure_advance_scale", 1.0)
    )
    pa_smooth = float(sc.get("pressure_advance_smooth_time", 0.03))
    flow_max = float(pack.max_volumetric_flow_mm3_s) * float(
        noz_bias.get("max_volumetric_flow_scale", 1.0)
    )

    first_spd = float(
        fl.get("speed_mm_s", surf_bias.get("first_layer_speed_mm_s", 18))
    )
    # Adhesion-limited: surface pack caps speed (PEX basement policy)
    surf_cap = float(surf_bias.get("first_layer_speed_mm_s", first_spd))
    first_spd = min(first_spd, surf_cap) * float(noz_bias.get("first_layer_speed_scale", 1.0))

    notes = []
    notes.extend([str(n) for n in pack.notes[:3]])
    notes.extend([str(n) for n in list(surf.get("notes_research", [])[:2])])
    notes.extend([str(n) for n in list(noz.get("notes_research", [])[:2])])

    # nozzle type token for macros
    if pack.abrasive:
        type_token = "hardened"
    else:
        type_token = str(noz.get("preflight", {}).get("type_token", "brozzl_plated_copper"))

    ret_len = float(ret.get("length_mm", 1.15)) * float(noz_bias.get("retract_length_scale", 1.0))
    ret_spd = float(ret.get("speed_mm_s", 40)) * float(noz_bias.get("retract_speed_scale", 1.0))

    return StackProfile(
        filament_sku=pack.sku,
        surface_sku=str(surf.get("sku", surface_sku)),
        nozzle_sku=str(noz.get("sku", nozzle_sku)),
        nozzle_diameter_mm=float(noz.get("nozzle", {}).get("diameter_mm", 0.4)),
        nozzle_type_token=type_token,
        abrasive=bool(pack.abrasive),
        bed_c=bed,
        nozzle_c=noz_c,
        soak_min=round(soak, 2),
        first_layer_height_mm=float(fl.get("height_mm", surf_bias.get("first_layer_height_mm", 0.28))),
        first_layer_speed_mm_s=round(first_spd, 2),
        first_layer_flow=float(fl.get("flow", surf_bias.get("first_layer_flow", 1.06))),
        line_width_mm=float(fl.get("line_width_mm", 0.48)),
        retract_mm=round(ret_len, 3),
        retract_speed_mm_s=round(ret_spd, 1),
        unretract_speed_mm_s=float(ret.get("unretract_speed_mm_s", 30)),
        wipe_mm=float(ret.get("wipe_mm", 1.4)),
        wipe_speed_mm_s=float(ret.get("wipe_speed_mm_s", 80)),
        z_hop_mm=float(ret.get("z_hop_mm", 0.25)),
        outer_wall_speed_mm_s=float(pack.role_speeds_mm_s.get("outer_wall", 55)),
        travel_speed_mm_s=float(pack.role_speeds_mm_s.get("travel", 250)),
        pressure_advance=round(pa, 4),
        pressure_advance_smooth_time=pa_smooth,
        max_volumetric_flow_mm3_s=round(flow_max, 2),
        fan_layer_start=int(surf_bias.get("fan_layer_start", 3)),
        brim=bool(fl.get("brim", surf_bias.get("brim_default", True))),
        glue=bool((pack.raw.get("surface") or {}).get("glue", surf.get("surface", {}).get("glue_preferred", False))),
        z_adjust_seed=float(z_adjust_seed),
        notes=tuple(notes),
    )
