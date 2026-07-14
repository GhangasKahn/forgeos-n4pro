"""Real-time features from Moonraker telemetry (no camera required).

Vision cameras refine scores; telemetry alone still drives a live dynamic loop:
temps, Z, print progress, volumetric proxies, flat-volume residual from pack.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import time

from forgeos.flat_surface import residual_ridge_proxy_mm, machine_flat_pack


@dataclass
class TelemetryFeatures:
    ts: float
    printing: bool
    print_state: str
    filename: str
    progress: float
    z_adjust_mm: float
    nozzle_c: float
    nozzle_target_c: float
    bed_c: float
    bed_target_c: float
    tool_z_mm: float
    speed_factor: float
    extrude_factor: float
    # Derived
    heat_ready: bool
    first_layer_window: bool
    ridge_proxy_mm: float
    flat_volume_score: float  # 1 = perfect volume balance belief
    thermal_track_score: float  # how well temps track targets

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def extract_telemetry(
    status: Dict[str, Any],
    *,
    line_w: float = 0.44,
    layer_h: float = 0.28,
    spacing_ratio: float = 1.0,
    flow: float = 1.0,
    first_layer_z_max: float = 0.45,
) -> TelemetryFeatures:
    ps = status.get("print_stats") or {}
    e = status.get("extruder") or {}
    b = status.get("heater_bed") or {}
    gm = status.get("gcode_move") or {}
    th = status.get("toolhead") or {}
    vs = status.get("virtual_sdcard") or {}

    state = str(ps.get("state") or "standby")
    printing = state.lower() == "printing"
    origin = gm.get("homing_origin") or [0, 0, 0, 0]
    z_adj = float(origin[2] if len(origin) > 2 else 0.0)
    gpos = gm.get("gcode_position") or [0, 0, 0]
    tool_z = float(gpos[2] if len(gpos) > 2 else 0.0)
    noz = float(e.get("temperature") or 0.0)
    noz_t = float(e.get("target") or 0.0)
    bed = float(b.get("temperature") or 0.0)
    bed_t = float(b.get("target") or 0.0)
    prog = float(vs.get("progress") or 0.0)
    sf = float(gm.get("speed_factor") or 1.0)
    ef = float(gm.get("extrude_factor") or 1.0)

    spacing = line_w * spacing_ratio
    ridge = residual_ridge_proxy_mm(line_w, layer_h, spacing, flow * ef)
    # map ridge to score: 0 mm → 1.0, ≥0.08 mm → 0
    flat_vol = max(0.0, min(1.0, 1.0 - ridge / 0.08))

    def track(actual: float, target: float) -> float:
        if target <= 1.0:
            return 0.5
        err = abs(actual - target)
        return max(0.0, min(1.0, 1.0 - err / 15.0))

    thermal = 0.5 * (track(noz, noz_t) + track(bed, bed_t))
    heat_ready = (noz_t <= 0 or noz >= noz_t - 3) and (bed_t <= 0 or bed >= bed_t - 2)
    # crude first-layer window: printing and tool Z near first layer
    fl_window = printing and tool_z <= first_layer_z_max and prog < 0.25

    return TelemetryFeatures(
        ts=time.time(),
        printing=printing,
        print_state=state,
        filename=str(ps.get("filename") or ""),
        progress=prog,
        z_adjust_mm=z_adj,
        nozzle_c=noz,
        nozzle_target_c=noz_t,
        bed_c=bed,
        bed_target_c=bed_t,
        tool_z_mm=tool_z,
        speed_factor=sf,
        extrude_factor=ef,
        heat_ready=heat_ready,
        first_layer_window=fl_window,
        ridge_proxy_mm=ridge,
        flat_volume_score=flat_vol,
        thermal_track_score=thermal,
    )


def default_pack_geometry() -> Dict[str, float]:
    p = machine_flat_pack()
    fl = p["first_layer"]
    return {
        "line_w": fl.line_width_mm,
        "layer_h": fl.layer_height_mm,
        "spacing_ratio": fl.spacing_ratio,
        "flow": fl.flow,
    }
