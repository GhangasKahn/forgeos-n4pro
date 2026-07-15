"""Calibration math, protocol, patterns, runner, promote — god-tier suite tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forgeos.calibration.math_cal import (
    N4PRO_MESH_P2P_MAX_MM,
    compute_flow_multiplier,
    compute_pressure_advance,
    compute_rotation_distance,
    dimensional_error_100mm,
    mesh_peak_to_peak,
    precision_span,
    suggest_z_nudge_from_first_layer,
)
from forgeos.calibration.patterns import (
    generate_extrude_cal_script,
    generate_first_layer_patch,
    generate_flow_shell,
    generate_pa_fine_tower,
    generate_pa_tower,
)
from forgeos.calibration.promote import (
    CalRecipe,
    apply_measurement_to_recipe,
    evaluate_dim_gates,
    promote_recipe,
)
from forgeos.calibration.protocol import (
    CalSuite,
    OperatorMode,
    build_plan,
    step_by_id,
    steps_for_suite,
)
from forgeos.calibration.runner import CalibrationRunner, StepStatus
from forgeos.campaigns.dimensional_fit import DimSample
from forgeos.campaigns.full_cal import FullCalCampaign
from forgeos.gates.verification import GateStatus
from forgeos.journal import Journal
from forgeos.moonraker_client import MoonrakerClient
from forgeos.safety import SafetyError, SafetyGate


# ---- math ----------------------------------------------------------------


def test_rotation_distance_under_extrusion_lowers_rd():
    r = compute_rotation_distance(7.5, commanded_mm=100.0, actual_mm=95.0)
    assert r.new_rotation_distance < 7.5
    assert abs(r.new_rotation_distance - 7.125) < 1e-4


def test_rotation_distance_rejects_bad_inputs():
    with pytest.raises(ValueError):
        compute_rotation_distance(0, 100, 100)


def test_flow_multiplier_from_thick_wall():
    # measured thicker than expected → lower flow
    r = compute_flow_multiplier(0.50, line_width_mm=0.44, current_flow=1.0)
    assert r.new_flow < 1.0
    assert r.expected_wall_mm == pytest.approx(0.44)


def test_flow_clamped_to_band():
    r = compute_flow_multiplier(0.20, line_width_mm=0.44, current_flow=1.0)
    assert r.new_flow <= 1.15


def test_pressure_advance_dd_factor():
    r = compute_pressure_advance(6.0, start=0.0, factor=0.005)
    assert r.pressure_advance == pytest.approx(0.030)


def test_mesh_and_dim_helpers():
    assert mesh_peak_to_peak([[0.0, 0.1], [-0.05, 0.12]]) == pytest.approx(0.17)
    assert dimensional_error_100mm(100.0, 99.8) == pytest.approx(-0.2)
    assert precision_span([99.9, 100.0, 99.95]) == pytest.approx(0.1)
    assert suggest_z_nudge_from_first_layer(ribs=True) > 0
    assert suggest_z_nudge_from_first_layer(under_squish=True) < 0


# ---- protocol ------------------------------------------------------------


def test_onetime_plan_has_openneptune_order():
    plan = build_plan(CalSuite.ONETIME, has_adxl=False)
    ids = [s.id for s in plan.steps]
    assert ids[0] == "preflight"
    assert ids.index("rotation_distance") < ids.index("flow")
    assert ids.index("flow") < ids.index("pressure_advance")
    assert "pid" in ids
    assert "probe_z" in ids
    assert "promote" in ids


def test_finetune_has_gates():
    steps = steps_for_suite(CalSuite.FINETUNE)
    ids = [s.id for s in steps]
    assert "g4_precision" in ids
    assert "g5_speed" in ids
    assert "pa_fine" in ids


def test_full_suite_concatenates():
    full = steps_for_suite(CalSuite.FULL)
    assert len(full) == len(steps_for_suite(CalSuite.ONETIME)) + len(
        steps_for_suite(CalSuite.FINETUNE)
    )


def test_optional_filter():
    steps = steps_for_suite(CalSuite.ONETIME, include_optional=False)
    assert all(s.operator != OperatorMode.OPTIONAL for s in steps)


def test_step_by_id():
    assert step_by_id("pid") is not None
    assert step_by_id("nope") is None


# ---- patterns ------------------------------------------------------------


def test_patterns_emit_klipper_safe_gcode():
    flow = generate_flow_shell()
    assert "FORGE_PRINT_START_ENV" in flow
    assert "G1" in flow
    pa = generate_pa_tower()
    assert "TUNING_TOWER" in pa
    assert "SET_PRESSURE_ADVANCE" in pa
    fl = generate_first_layer_patch()
    assert "FORGE_PURGE" in fl
    assert generate_extrude_cal_script().count("G1 E") >= 1
    fine = generate_pa_fine_tower(seed_pa=0.030)
    assert "TUNING_TOWER" in fine


# ---- runner dry-run ------------------------------------------------------


def test_runner_dry_run_full_campaign(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    runner = CalibrationRunner(journal=j, safety=SafetyGate(), artifacts_dir=tmp_path / "cal")
    runner.start(CalSuite.FULL, dry_run=True, has_adxl=False)
    report = runner.run_all_dry()
    assert not report.failed
    assert len(report.results) >= 15
    # resonance should skip without adxl
    res = [r for r in report.results if r.step_id == "resonance"]
    assert res and res[0].status == StepStatus.SKIPPED
    # flow pattern written
    assert (tmp_path / "cal" / "forgeos_cal_flow.gcode").is_file()
    path = runner.write_report(report)
    data = json.loads(path.read_text())
    assert data["suite"] == "full"


def test_runner_requires_arm_for_execute(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    client = MoonrakerClient(host="127.0.0.1", port=9)  # unused
    runner = CalibrationRunner(
        journal=j, safety=SafetyGate(), client=client, artifacts_dir=tmp_path / "cal"
    )
    with pytest.raises(SafetyError):
        runner.start(CalSuite.ONETIME, dry_run=False, execute=True)


def test_runner_evidence_updates_recipe(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    runner = CalibrationRunner(journal=j, safety=SafetyGate(), artifacts_dir=tmp_path / "cal")
    runner.start(CalSuite.ONETIME, dry_run=True)
    # advance to flow
    while runner.current_step and runner.current_step.id != "flow":
        r = runner.run_current()
        if r.status == StepStatus.WAITING_OPERATOR:
            runner.submit_evidence({"ok": True}, ok=True)
        elif r.status == StepStatus.SKIPPED:
            pass
        runner.advance()
    assert runner.current_step and runner.current_step.id == "flow"
    runner.run_current(auto_pass_dry=False)
    runner.submit_evidence({"wall_mm": 0.48}, ok=True)
    assert runner.recipe.flow < 1.0


# ---- promote / gates -----------------------------------------------------


def test_promote_writes_saved_state(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    recipe = CalRecipe(pressure_advance=0.032, flow=0.98, z_adjust_mm=-0.480)
    recipe.abs_error_100mm = 0.08
    state = tmp_path / "configs" / "saved_state.yaml"
    state.parent.mkdir(parents=True)
    state.write_text("version: 1\nprocess: {}\n", encoding="utf-8")
    samples = [DimSample("X", 100.0, 99.92)]
    report = evaluate_dim_gates(samples)
    assert report.results[0].status == GateStatus.PASS
    out = promote_recipe(j, recipe, report=report, saved_state_path=state)
    assert out["feasible"] is True
    text = state.read_text()
    assert "0.032" in text
    assert "restore_gcode" in text or "FORGE_SET_PA" in text


def test_apply_measurement_to_recipe():
    r = CalRecipe()
    r2 = apply_measurement_to_recipe(
        r,
        flow_wall_mm=0.46,
        pa_height_mm=6.0,
        rotation_distance_current=7.5,
        rotation_actual_mm=100.0,
    )
    assert r2.pressure_advance == pytest.approx(0.030)
    assert r2.rotation_distance == pytest.approx(7.5)


def test_g4_g5_in_evaluate():
    samples = [DimSample("X", 100.0, 99.95)]
    report = evaluate_dim_gates(
        samples,
        replicate_measurements=[99.95, 99.97, 99.93],
        duration_s=900,
        baseline_s=1400,
    )
    ids = {r.gate_id: r.status for r in report.results}
    assert ids["G3"] == GateStatus.PASS
    assert ids["G4"] == GateStatus.PASS
    assert ids["G5"] == GateStatus.PASS


# ---- legacy campaign bridge ----------------------------------------------


def test_full_cal_protocol_plan(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    g = SafetyGate()
    c = FullCalCampaign(journal=j, safety=g)
    plan = c.full_protocol_plan(has_adxl=True)
    assert plan.suite == CalSuite.FULL
    assert any(s.id == "resonance" for s in plan.steps)


def test_mesh_p2p_gate_constant():
    assert N4PRO_MESH_P2P_MAX_MM == 0.80
