"""Analyze calibration measurements — mesh, PA, flow, gates, precision."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from forgeos.calibration.types import CalAnalysis, CalMeasurement
from forgeos.gates.verification import GateResult, GateStatus, gate_g3_accuracy, gate_g4_precision


def analyze_mesh_matrix(matrix: Sequence[Sequence[float]]) -> CalAnalysis:
    """Compute peak-to-peak from Klipper probed_matrix."""
    vals = [float(v) for row in matrix for v in row]
    if not vals:
        return CalAnalysis(
            "mesh_precision",
            False,
            "empty mesh matrix",
            evidence={"point_count": 0},
        )
    p2p = max(vals) - min(vals)
    excellent = p2p <= 0.25
    preferred = p2p <= 0.40
    hard_ok = p2p <= 0.80
    passed = hard_ok
    recs: List[str] = []
    if not preferred:
        recs.append("Run BED_LEVEL_SCREWS_TUNE then re-mesh; check corner nuts")
    if not excellent:
        recs.append("Consider mechanical re-level before chasing slicer Z")
    tier = "excellent" if excellent else "preferred" if preferred else "acceptable" if hard_ok else "fail"
    return CalAnalysis(
        "mesh_precision",
        passed,
        "mesh p2p=%.3f mm (%s)" % (p2p, tier),
        evidence={
            "peak_to_peak_mm": round(p2p, 4),
            "min_mm": round(min(vals), 4),
            "max_mm": round(max(vals), 4),
            "point_count": len(vals),
            "tier": tier,
        },
        recommendations=recs,
    )


def analyze_pa_tower_height(
    sharp_layer_height_mm: float,
    start_pa: float = 0.0,
    step_factor: float = 0.005,
    layer_height_mm: float = 0.2,
) -> CalAnalysis:
    """Klipper TUNING_TOWER PA: height to sharpest corner × factor + start."""
    layer_idx = max(0.0, sharp_layer_height_mm / layer_height_mm)
    pa = start_pa + layer_idx * step_factor
    pa = max(0.0, min(0.2, pa))
    return CalAnalysis(
        "pressure_advance",
        True,
        "PA=%.4f from tower height %.2f mm" % (pa, sharp_layer_height_mm),
        evidence={
            "pressure_advance": round(pa, 4),
            "sharp_height_mm": sharp_layer_height_mm,
            "layer_index": round(layer_idx, 2),
            "step_factor": step_factor,
        },
        recommendations=["SET_PRESSURE_ADVANCE ADVANCE=%.4f" % pa],
    )


def analyze_flow_wall_thickness(
    measured_wall_mm: float,
    line_width_mm: float,
    nozzle_diameter_mm: float = 0.4,
) -> CalAnalysis:
    """Single-wall flow: compare measured wall to expected line width."""
    expected = line_width_mm
    ratio = measured_wall_mm / expected if expected > 0 else 0.0
    flow_pct = ratio * 100.0
    # ±5% is typical acceptable band for fixture work
    passed = 95.0 <= flow_pct <= 105.0
    recs: List[str] = []
    if flow_pct < 95.0:
        recs.append("Increase flow multiplier by ~%.1f%%" % (100.0 - flow_pct))
    elif flow_pct > 105.0:
        recs.append("Decrease flow multiplier by ~%.1f%%" % (flow_pct - 100.0))
    return CalAnalysis(
        "flow_rate",
        passed,
        "flow=%.1f%% (wall %.3f vs line %.3f)" % (flow_pct, measured_wall_mm, expected),
        evidence={
            "flow_percent": round(flow_pct, 2),
            "measured_wall_mm": measured_wall_mm,
            "line_width_mm": line_width_mm,
            "nozzle_diameter_mm": nozzle_diameter_mm,
        },
        recommendations=recs,
    )


def analyze_temp_tower_layer(
    best_layer_height_mm: float,
    start_temp_c: float = 200.0,
    step_delta_c: float = 5.0,
    layer_height_mm: float = 5.0,
) -> CalAnalysis:
    """Temperature tower: layer height to best surface × step + start."""
    layer_idx = max(0, int(round(best_layer_height_mm / layer_height_mm)) - 1)
    temp_c = start_temp_c + layer_idx * step_delta_c
    return CalAnalysis(
        "temperature_tower",
        True,
        "nozzle=%.0f C from tower layer at %.1f mm" % (temp_c, best_layer_height_mm),
        evidence={
            "nozzle_temp_c": temp_c,
            "best_layer_height_mm": best_layer_height_mm,
            "layer_index": layer_idx,
        },
        recommendations=["Set filament profile nozzle temp to %.0f C" % temp_c],
    )


def analyze_retraction_tower(
    clean_layer_height_mm: float,
    start_mm: float = 0.5,
    step_mm: float = 0.5,
    layer_height_mm: float = 1.0,
) -> CalAnalysis:
    """Retraction tower: height to cleanest layer × step + start."""
    layer_idx = max(0, int(round(clean_layer_height_mm / layer_height_mm)) - 1)
    retract_mm = start_mm + layer_idx * step_mm
    return CalAnalysis(
        "retraction_distance",
        True,
        "retract=%.2f mm from tower height %.1f mm" % (retract_mm, clean_layer_height_mm),
        evidence={
            "retract_mm": round(retract_mm, 3),
            "clean_height_mm": clean_layer_height_mm,
        },
        recommendations=["FORGE_SET_RETRACT LENGTH=%.2f" % retract_mm],
    )


def analyze_precision_span(measurements_mm: Sequence[float], nominal_mm: float = 100.0) -> CalAnalysis:
    """G4 precision: span across replicate prints."""
    if len(measurements_mm) < 2:
        return CalAnalysis("precision_replicate", False, "need >=2 measurements")
    span = max(measurements_mm) - min(measurements_mm)
    errors = [m - nominal_mm for m in measurements_mm]
    g4 = gate_g4_precision(span)
    return CalAnalysis(
        "precision_replicate",
        g4.status == GateStatus.PASS,
        g4.detail,
        evidence={
            "span_mm": round(span, 4),
            "measurements_mm": list(measurements_mm),
            "errors_mm": [round(e, 4) for e in errors],
            "mean_error_mm": round(sum(errors) / len(errors), 4),
            "gate": g4.as_dict(),
        },
    )


def analyze_accuracy_error(measured_mm: float, nominal_mm: float = 100.0) -> CalAnalysis:
    """G3 accuracy: single measurement vs nominal."""
    err = measured_mm - nominal_mm
    g3 = gate_g3_accuracy(err)
    return CalAnalysis(
        "dimensional_accuracy",
        g3.status == GateStatus.PASS,
        g3.detail,
        evidence={
            "measured_mm": measured_mm,
            "nominal_mm": nominal_mm,
            "error_mm": round(err, 4),
            "abs_error_mm": round(abs(err), 4),
            "gate": g3.as_dict(),
        },
    )


def gate_result_from_measurement(measurement: CalMeasurement) -> Optional[GateResult]:
    """Map a CalMeasurement to a zero-trust gate result when applicable."""
    tid = measurement.test_id
    v = measurement.values
    if tid == "dimensional_accuracy":
        err = float(v.get("error_mm", v.get("measured_mm", 0) - v.get("nominal_mm", 100.0)))
        return gate_g3_accuracy(err)
    if tid == "precision_replicate":
        return gate_g4_precision(float(v.get("span_mm", 999.0)))
    if tid == "mesh_precision":
        p2p = float(v.get("peak_to_peak_mm", 999.0))
        from forgeos.gates.verification import gate_g2_process_sensors

        return gate_g2_process_sensors(p2p, shaper_ok=bool(v.get("shaper_ok", True)), thermal_stable=True)
    return None


def analyze_measurement(defn_id: str, values: Dict[str, Any]) -> CalAnalysis:
    """Dispatch analysis by test id."""
    m = CalMeasurement(defn_id, values)
    if defn_id == "mesh_precision" and "matrix" in values:
        return analyze_mesh_matrix(values["matrix"])
    if defn_id == "pressure_advance":
        return analyze_pa_tower_height(float(values["sharp_height_mm"]))
    if defn_id == "flow_rate":
        return analyze_flow_wall_thickness(
            float(values["measured_wall_mm"]),
            float(values.get("line_width_mm", 0.44)),
        )
    if defn_id == "temperature_tower":
        return analyze_temp_tower_layer(float(values["best_layer_height_mm"]))
    if defn_id == "retraction_distance":
        return analyze_retraction_tower(float(values["clean_height_mm"]))
    if defn_id == "dimensional_accuracy":
        return analyze_accuracy_error(
            float(values["measured_mm"]),
            float(values.get("nominal_mm", 100.0)),
        )
    if defn_id == "precision_replicate":
        return analyze_precision_span(values["measurements_mm"])
    if defn_id == "speed_regression":
        t0 = float(values.get("baseline_s", 0))
        t1 = float(values.get("trial_s", 0))
        from forgeos.gates.verification import gate_g5_speed

        g5 = gate_g5_speed(t1, t0)
        return CalAnalysis(
            defn_id,
            g5.status.value == "pass",
            g5.detail,
            evidence=g5.evidence,
        )
    return CalAnalysis(defn_id, True, "no automated analysis for %s" % defn_id, evidence=values)
