"""One-shot helper: build before/during/after plans for a shop session."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from forgeos.environment.homeostasis import HomeostasisController
from forgeos.environment.loader import load_environment_profile
from forgeos.environment.models import AmbientReading, EnclosureMode, Phase
from forgeos.materials import MaterialPack, load_material_pack, default_materials_dir
from forgeos.sensors.moisture_soft_sensor import MoistureEstimate


def build_session_plan(
    material_sku: str = "protopasta_htpla",
    ambient: Optional[AmbientReading] = None,
    env_profile_path: Optional[Path] = None,
    moisture: Optional[MoistureEstimate] = None,
    materials_dir: Optional[Path] = None,
    memory: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mdir = materials_dir or default_materials_dir()
    pack = load_material_pack(mdir / ("%s.yaml" % material_sku))
    if ambient is None:
        if env_profile_path is not None:
            ambient = load_environment_profile(env_profile_path).ambient
        else:
            ambient = AmbientReading(
                temperature_c=14.0,
                rh_percent=65.0,
                enclosure=EnclosureMode.OPEN,
                draft_level=0.3,
                source="session_default_basement",
            )
    ctrl = HomeostasisController(material=pack, ambient=ambient, moisture=moisture)
    if memory:
        ctrl.import_memory(memory)
    plans = {
        "before": ctrl.plan_phase(Phase.BEFORE).as_dict(),
        "during": ctrl.plan_phase(Phase.DURING).as_dict(),
        "after": ctrl.plan_phase(Phase.AFTER).as_dict(),
    }
    return {
        "material": pack.sku,
        "ambient": ambient.as_dict(),
        "bin": ambient.environment_bin().value,
        "homeostasis_key": ctrl.bin_key(),
        "homeostasis_state": ctrl.get_state().as_dict(),
        "plans": plans,
    }
