"""Comprehensive calibration suite tests."""

from __future__ import annotations

import json
import math

import pytest

from forgeos.calibration.analysis import (
    analyze_accuracy_error,
    analyze_flow_wall_thickness,
    analyze_mesh_matrix,
    analyze_measurement,
    analyze_pa_tower_height,
    analyze_precision_span,
    analyze_temp_tower_layer,
    gate_result_from_measurement,
)
from forgeos.calibration.gcodes import (
    gcode_first_layer_panel,
    gcode_pa_tower_prep,
    gcode_single_wall_cube,
    rotation_distance_from_measurement,
)
from forgeos.calibration.registry import (
    CALIBRATION_CATALOG,
    FULL_CAMPAIGN_SEQUENCE,
    FINE_TUNE_SEQUENCE,
    ONE_TIME_SEQUENCE,
    gate_tests,
    get_calibration_test,
    one_time_tests,
    calibration_tests_for_category,
)
from forgeos.calibration.runner import CalibrationRunner
from forgeos.calibration.types import CalCategory, CalMeasurement, CalPhase
from forgeos.campaigns.full_cal import CalStep, FullCalCampaign
from forgeos.gates.verification import GateStatus
from forgeos.journal import Journal
from forgeos.safety import SafetyError, SafetyGate


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------


def test_catalog_has_all_categories():
    cats = {t.category for t in CALIBRATION_CATALOG.values()}
    assert CalCategory.ONE_TIME in cats
    assert CalCategory.FINE_TUNE in cats
    assert CalCategory.GATE in cats
    assert CalCategory.PERIODIC in cats


def test_one_time_sequence_covers_neptune_basics():
    required = {
        "pid_extruder",
        "probe_z_offset",
        "bed_screws_tilt",
        "mesh_golden",
        "rotation_distance",
    }
    assert required.issubset(set(ONE_TIME_SEQUENCE))


def test_fine_tune_includes_pa_flow_z():
    ids = set(FINE_TUNE_SEQUENCE)
    assert "pressure_advance" in ids
    assert "flow_rate" in ids
    assert "z_offset_live" in ids
    assert "temperature_tower" in ids


def test_full_campaign_sequence_order():
    assert FULL_CAMPAIGN_SEQUENCE.index("probe_z_offset") < FULL_CAMPAIGN_SEQUENCE.index("mesh_golden")
    assert FULL_CAMPAIGN_SEQUENCE.index("flow_rate") < FULL_CAMPAIGN_SEQUENCE.index("dimensional_accuracy")


def test_openneptune_macro_mappings():
    probe = get_calibration_test("probe_z_offset")
    assert probe is not None
    assert probe.openneptune_macro == "CALIBRATE_PROBE_Z_OFFSET"
    screws = get_calibration_test("bed_screws_tilt")
    assert screws.openneptune_macro == "BED_LEVEL_SCREWS_TUNE"
    shaper = get_calibration_test("input_shaper")
    assert shaper.openneptune_macro == "SHAPER_CALIBRATE"


def test_gate_tests_have_pass_criteria():
    for t in gate_tests():
        assert t.pass_criteria, "%s missing pass_criteria" % t.id


def test_n4_pro_dual_bed_tests():
    outer = get_calibration_test("pid_bed_outer")
    assert outer is not None
    assert "heater_bed_outer" in outer.klipper_commands[0]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def test_mesh_analysis_excellent():
    matrix = [[0.0, 0.1, 0.2], [0.05, 0.15, 0.25], [0.1, 0.2, 0.25]]
    r = analyze_mesh_matrix(matrix)
    assert r.passed
    assert r.evidence["peak_to_peak_mm"] == pytest.approx(0.25, abs=0.01)
    assert r.evidence["tier"] == "excellent"


def test_mesh_analysis_fail():
    matrix = [[0.0, 0.5, 1.0], [0.2, 0.8, 1.2]]
    r = analyze_mesh_matrix(matrix)
    assert not r.passed


def test_pa_tower_analysis():
    # 12.5 mm / 0.2 layer = layer 62.5 → PA = 0 + 62.5 * 0.005 = 0.3125 capped
    r = analyze_pa_tower_height(12.5, start_pa=0.0, step_factor=0.005, layer_height_mm=0.2)
    assert r.passed
    assert 0.02 <= r.evidence["pressure_advance"] <= 0.2


def test_flow_analysis_pass():
    r = analyze_flow_wall_thickness(0.44, 0.44)
    assert r.passed
    assert r.evidence["flow_percent"] == pytest.approx(100.0, abs=0.1)


def test_flow_analysis_under():
    r = analyze_flow_wall_thickness(0.40, 0.44)
    assert not r.passed
    assert any("Increase" in rec for rec in r.recommendations)


def test_g3_accuracy_pass_fail():
    assert analyze_accuracy_error(100.10, 100.0).passed
    assert not analyze_accuracy_error(100.25, 100.0).passed


def test_g4_precision_span():
    assert analyze_precision_span([100.0, 100.05, 99.98]).passed
    assert not analyze_precision_span([100.0, 100.15, 99.90]).passed


def test_temp_tower_analysis():
    r = analyze_temp_tower_layer(10.0, start_temp_c=200.0, step_delta_c=5.0, layer_height_mm=5.0)
    assert r.evidence["nozzle_temp_c"] == 205.0


def test_gate_result_from_measurement_g3():
    m = CalMeasurement("dimensional_accuracy", {"error_mm": 0.15})
    g = gate_result_from_measurement(m)
    assert g is not None
    assert g.status == GateStatus.PASS


def test_analyze_measurement_dispatch():
    r = analyze_measurement("flow_rate", {"measured_wall_mm": 0.44, "line_width_mm": 0.44})
    assert r.test_id == "flow_rate"
    assert r.passed


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def test_runner_plan_one_time():
    runner = CalibrationRunner()
    plan = runner.plan_report("one_time")
    assert plan["test_count"] >= len(ONE_TIME_SEQUENCE) - 1  # may skip shaper in live
    assert plan["estimated_duration_min"] > 60


def test_runner_plan_fine_tune():
    plan = CalibrationRunner().plan_report("fine_tune")
    assert plan["mode"] == "fine_tune"
    assert plan["test_count"] == len(FINE_TUNE_SEQUENCE)


def test_runner_record_measurement(tmp_path):
    j = Journal(tmp_path / "cal.sqlite3")
    runner = CalibrationRunner(journal=j)
    r = runner.record_measurement("dimensional_accuracy", {"measured_mm": 100.05, "nominal_mm": 100.0})
    assert r.status == "ok"
    assert r.analysis is not None
    assert runner.summary()["passed"] == 1


def test_runner_dry_run_live(tmp_path):
    j = Journal(tmp_path / "cal.sqlite3")
    safety = SafetyGate()
    tok = safety.arm("campaign")
    runner = CalibrationRunner(journal=j, safety=safety, client=None)
    runner.arm(tok)
    # No client — only dry_run path works without client for individual steps
    runner.results.append(
        runner.run_live_step(get_calibration_test("pid_extruder"), dry_run=True)  # type: ignore[arg-type]
    )
    assert runner.results[0].status == "ok"


def test_runner_live_requires_arm():
    runner = CalibrationRunner()
    with pytest.raises(SafetyError):
        runner.run_live_sequence("one_time", dry_run=False)


# ---------------------------------------------------------------------------
# Campaign integration
# ---------------------------------------------------------------------------


def test_campaign_full_flow_skips_shaper(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    g = SafetyGate()
    c = FullCalCampaign(journal=j, safety=g, skip_shaper=True)
    tok = g.arm("campaign")
    c.start(tok)
    assert c.step == CalStep.PID
    c.advance(True)  # -> skips shaper -> PROBE_Z
    assert c.step == CalStep.PROBE_Z
    while c.step not in {CalStep.DONE, CalStep.FAILED, CalStep.MEASURE}:
        c.advance(True)
    c.advance(True)
    assert c.step == CalStep.DONE


def test_campaign_scripts_for_pid(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    g = SafetyGate()
    c = FullCalCampaign(journal=j, safety=g)
    tok = g.arm("campaign")
    c.start(tok)
    assert "FORGE_PID_ALL" in c.moonraker_scripts_for_step()


def test_campaign_runner_plan(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    g = SafetyGate()
    c = FullCalCampaign(journal=j, safety=g)
    plan = c.runner_plan()
    assert plan["mode"] == "full"
    assert plan["test_count"] > 5


# ---------------------------------------------------------------------------
# G-code generators
# ---------------------------------------------------------------------------


def test_pa_tower_prep_commands():
    cmds = gcode_pa_tower_prep()
    assert any("TUNING_TOWER" in c for c in cmds)
    assert any("SET_VELOCITY_LIMIT" in c for c in cmds)


def test_flow_cube_gcode_has_extrusion():
    g = gcode_single_wall_cube()
    assert "G1" in g
    assert "E" in g
    assert "single-wall" in g


def test_first_layer_panel_gcode():
    g = gcode_first_layer_panel()
    assert "first-layer" in g
    assert g.count("G1") >= 3


def test_rotation_distance_math():
    new_rd = rotation_distance_from_measurement(22.678, 100.0, 98.0)
    assert new_rd == pytest.approx(22.678 * (100.0 / 98.0), rel=1e-4)


def test_rotation_distance_invalid():
    with pytest.raises(ValueError):
        rotation_distance_from_measurement(22.0, 100.0, 0.0)


# ---------------------------------------------------------------------------
# Catalog JSON round-trip
# ---------------------------------------------------------------------------


def test_catalog_serializable():
    for tid, t in CALIBRATION_CATALOG.items():
        d = t.as_dict()
        blob = json.dumps(d)
        loaded = json.loads(blob)
        assert loaded["id"] == tid


def test_tests_for_category_gate_only():
    gates = calibration_tests_for_category(CalCategory.GATE)
    assert all(t.category == CalCategory.GATE for t in gates)
    assert len(gates) >= 4


def test_one_time_count():
    assert len(one_time_tests()) >= 9
