"""Measure → gate → promote calibration results into journal + saved_state."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import time

import yaml

from forgeos.campaigns.dimensional_fit import DimSample, fit_scales
from forgeos.calibration.math_cal import (
    compute_flow_multiplier,
    compute_pressure_advance,
    compute_rotation_distance,
    dimensional_error_100mm,
    precision_span,
)
from forgeos.gates.verification import (
    GateResult,
    GateStatus,
    VerificationReport,
    gate_g3_accuracy,
    gate_g4_precision,
    gate_g5_speed,
    gate_g6_anneal,
)
from forgeos.journal import Journal
from forgeos.optim.multi_objective import score_observation
from forgeos.optim.quality_score import PillarObservation


@dataclass
class CalRecipe:
    """Process knobs promoted after a successful calibration campaign."""

    sku: str = "protopasta_htpla"
    z_adjust_mm: float = -0.480
    bed_c: float = 65.0
    nozzle_c: float = 214.0
    soak_min: float = 5.0
    pressure_advance: float = 0.030
    pressure_advance_smooth_time: float = 0.03
    flow: float = 1.00
    retract_mm: float = 1.20
    retract_speed_mm_s: float = 40.0
    wipe_mm: float = 1.4
    z_hop_mm: float = 0.25
    rotation_distance: Optional[float] = None
    mesh_p2p_mm: Optional[float] = None
    abs_error_100mm: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def restore_gcode(self) -> str:
        lines = [
            'FORGE_SET_SURFACE TYPE=pex NAME="WhamBam PEX"',
            "FORGE_SET_NOZZLE TYPE=brozzl_plated_copper DIA=0.4",
            "FORGE_SET_MATERIAL SKU=%s" % self.sku,
            "FORGE_SET_Z_ADJUST Z=%.3f" % self.z_adjust_mm,
            "FORGE_APPLY_ENV_TARGETS BED=%.1f NOZ=%.1f SOAK=%.2f"
            % (self.bed_c, self.nozzle_c, self.soak_min),
            "FORGE_SET_RETRACT LENGTH=%.2f SPEED=%.0f WIPE=%.2f ZHOP=%.2f"
            % (self.retract_mm, self.retract_speed_mm_s, self.wipe_mm, self.z_hop_mm),
            "FORGE_SET_PA PA=%.4f SMOOTH=%.3f"
            % (self.pressure_advance, self.pressure_advance_smooth_time),
            "FORGE_SET_FLOW FLOW=%.0f" % (self.flow * 100.0),
            "FORGE_PREFLIGHT",
            "FORGE_Z_STATUS",
        ]
        return "\n".join(lines) + "\n"


def apply_measurement_to_recipe(
    recipe: CalRecipe,
    *,
    flow_wall_mm: Optional[float] = None,
    line_width_mm: float = 0.44,
    pa_height_mm: Optional[float] = None,
    pa_start: float = 0.0,
    pa_factor: float = 0.005,
    rotation_distance_current: Optional[float] = None,
    rotation_actual_mm: Optional[float] = None,
    rotation_commanded_mm: float = 100.0,
    z_adjust_mm: Optional[float] = None,
    nozzle_c: Optional[float] = None,
    retract_mm: Optional[float] = None,
) -> CalRecipe:
    r = CalRecipe(**recipe.as_dict())
    if flow_wall_mm is not None:
        fr = compute_flow_multiplier(flow_wall_mm, line_width_mm=line_width_mm, current_flow=r.flow)
        r.flow = fr.new_flow
        r.notes.append("flow from wall=%.3f → %.4f" % (flow_wall_mm, fr.new_flow))
    if pa_height_mm is not None:
        pr = compute_pressure_advance(pa_height_mm, start=pa_start, factor=pa_factor)
        r.pressure_advance = pr.pressure_advance
        r.notes.append("PA from height=%.2f → %.5f" % (pa_height_mm, pr.pressure_advance))
    if rotation_distance_current is not None and rotation_actual_mm is not None:
        rd = compute_rotation_distance(
            rotation_distance_current,
            commanded_mm=rotation_commanded_mm,
            actual_mm=rotation_actual_mm,
        )
        r.rotation_distance = rd.new_rotation_distance
        r.notes.append("RD %.5f → %.5f" % (rd.old_rotation_distance, rd.new_rotation_distance))
    if z_adjust_mm is not None:
        r.z_adjust_mm = float(z_adjust_mm)
    if nozzle_c is not None:
        r.nozzle_c = float(nozzle_c)
    if retract_mm is not None:
        r.retract_mm = float(retract_mm)
    return r


def evaluate_dim_gates(
    samples: List[DimSample],
    *,
    replicate_measurements: Optional[List[float]] = None,
    duration_s: Optional[float] = None,
    baseline_s: Optional[float] = None,
    post_anneal_err_mm: Optional[float] = None,
) -> VerificationReport:
    report = VerificationReport()
    fit = fit_scales(samples)
    # Prefer explicit 100 mm X error if present
    err100 = fit.mean_abs_error_100mm
    for s in samples:
        if s.axis.upper() == "X" and abs(s.nominal_mm - 100.0) < 1e-6:
            err100 = abs(dimensional_error_100mm(s.nominal_mm, s.measured_mm))
            break
    report.add(gate_g3_accuracy(err100))
    if replicate_measurements:
        span = precision_span(replicate_measurements)
        report.add(gate_g4_precision(span))
    if duration_s is not None and baseline_s is not None:
        report.add(gate_g5_speed(duration_s, baseline_s))
    if post_anneal_err_mm is not None:
        report.add(gate_g6_anneal(post_anneal_err_mm))
    return report


def promote_recipe(
    journal: Journal,
    recipe: CalRecipe,
    *,
    report: Optional[VerificationReport] = None,
    saved_state_path: Optional[Path] = None,
    j_score: Optional[float] = None,
) -> Dict[str, Any]:
    feasible = True
    if report is not None:
        g3 = next((r for r in report.results if r.gate_id == "G3"), None)
        feasible = g3 is not None and g3.status == GateStatus.PASS

    if j_score is None:
        err = float(recipe.abs_error_100mm or 0.10)
        obs = PillarObservation(
            duration_s=1200.0,
            baseline_s=1400.0,
            abs_error_100mm=err,
            precision_span_mm=0.05,
            first_layer_ok=True,
            delam=False,
        )
        j_score = float(score_observation(obs).j)

    payload = {
        "recipe": recipe.as_dict(),
        "gates": report.summary() if report else {},
        "ts": time.time(),
    }
    journal.promote_pack(
        sku=recipe.sku,
        recipe="cal_promote",
        j_score=float(j_score),
        feasible=feasible,
        payload=payload,
    )
    journal.log_event("cal_promote", payload)

    out: Dict[str, Any] = {"feasible": feasible, "recipe": recipe.as_dict(), "j_score": j_score}

    if saved_state_path is not None:
        path = Path(saved_state_path)
        data: Dict[str, Any] = {}
        if path.is_file():
            with path.open("r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
                if isinstance(loaded, dict):
                    data = loaded
        proc = dict(data.get("process") or {})
        proc.update(
            {
                "z_adjust_mm": recipe.z_adjust_mm,
                "bed_c": recipe.bed_c,
                "nozzle_c": recipe.nozzle_c,
                "soak_min": recipe.soak_min,
                "pressure_advance": recipe.pressure_advance,
                "pressure_advance_smooth_time": recipe.pressure_advance_smooth_time,
                "retract_mm": recipe.retract_mm,
                "retract_speed_mm_s": recipe.retract_speed_mm_s,
                "wipe_mm": recipe.wipe_mm,
                "z_hop_mm": recipe.z_hop_mm,
                "flow": recipe.flow,
            }
        )
        if recipe.rotation_distance is not None:
            proc["rotation_distance"] = recipe.rotation_distance
        data["process"] = proc
        data["restore_gcode"] = recipe.restore_gcode()
        data["calibration_promoted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False)
        out["saved_state"] = str(path)

        # JSON twin for tooling
        json_path = path.with_suffix(".json")
        # prefer artifacts/ if yaml is under configs/
        if "configs" in path.parts:
            json_path = path.parents[1] / "artifacts" / (path.stem + ".json")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
        out["saved_state_json"] = str(json_path)

    return out
