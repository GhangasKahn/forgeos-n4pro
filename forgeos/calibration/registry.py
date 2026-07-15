"""Full calibration catalog — Neptune 4 Pro + OpenNeptune alignment."""

from __future__ import annotations

from typing import Dict, List, Optional

from forgeos.calibration.types import CalCategory, CalPhase, CalTestDef

# ---------------------------------------------------------------------------
# ONE-TIME CALIBRATION (hardware install / major change)
# Research: OpenNeptune PID_TUNE_*, CALIBRATE_PROBE_Z_OFFSET, BED_LEVEL_SCREWS_TUNE,
# AXIS_TWIST_COMP_TUNE, SHAPER_CALIBRATE, rotation distance, golden mesh.
# ---------------------------------------------------------------------------

_ONE_TIME: List[CalTestDef] = [
    CalTestDef(
        id="pid_extruder",
        name="PID tune extruder",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.THERMAL,
        description="Stabilize hotend temperature for consistent melt and flow.",
        macro="FORGE_PID_EXTRUDER",
        klipper_commands=("PID_CALIBRATE HEATER=extruder TARGET=220", "SAVE_CONFIG"),
        openneptune_macro="PID_TUNE_EXTRUDER",
        duration_min=15.0,
        capture_fields=("pid_kp", "pid_ki", "pid_kd"),
        pass_criteria={"thermal_overshoot_c": 3.0},
    ),
    CalTestDef(
        id="pid_bed_inner",
        name="PID tune inner bed",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.THERMAL,
        description="Inner heater_bed zone — primary print surface on N4 Pro.",
        macro="FORGE_PID_BED_INNER",
        klipper_commands=("PID_CALIBRATE HEATER=heater_bed TARGET=65", "SAVE_CONFIG"),
        openneptune_macro="PID_TUNE_BED",
        duration_min=15.0,
        prerequisites=("pid_extruder",),
        capture_fields=("pid_kp", "pid_ki", "pid_kd"),
    ),
    CalTestDef(
        id="pid_bed_outer",
        name="PID tune outer bed",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.THERMAL,
        description="Outer heater_bed_outer zone — dual-bed equalization on N4 Pro.",
        macro="FORGE_PID_BED_OUTER",
        klipper_commands=("PID_CALIBRATE HEATER=heater_bed_outer TARGET=65", "SAVE_CONFIG"),
        openneptune_macro="PID_TUNE_OUTER_BED",
        duration_min=15.0,
        prerequisites=("pid_bed_inner",),
        capture_fields=("pid_kp", "pid_ki", "pid_kd"),
    ),
    CalTestDef(
        id="probe_z_offset",
        name="Probe Z offset (paper test)",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.GEOMETRY,
        description="Calibrate inductive probe z_offset cold; accept and SAVE_CONFIG.",
        macro="FORGE_PROBE_CAL",
        klipper_commands=("G28", "PROBE_CALIBRATE", "SAVE_CONFIG"),
        openneptune_macro="CALIBRATE_PROBE_Z_OFFSET",
        duration_min=10.0,
        prerequisites=("pid_bed_inner",),
        capture_fields=("z_offset_mm",),
        pass_criteria={"paper_drag": "pull_out_not_push_in"},
    ),
    CalTestDef(
        id="bed_screws_tilt",
        name="Bed leveling screws tilt",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.GEOMETRY,
        description="Corner screw adjustment via probe; run probe Z cal after.",
        macro="FORGE_SCREWS_TILT",
        klipper_commands=("G28", "BED_MESH_CLEAR", "BED_LEVEL_SCREWS_TUNE"),
        openneptune_macro="BED_LEVEL_SCREWS_TUNE",
        duration_min=15.0,
        prerequisites=("probe_z_offset",),
        capture_fields=("screw_adjustments",),
        pass_criteria={"post_step": "probe_z_offset"},
    ),
    CalTestDef(
        id="axis_twist",
        name="Axis twist compensation",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.GEOMETRY,
        description="Compensate X rail twist affecting first-layer uniformity.",
        macro="FORGE_AXIS_TWIST",
        klipper_commands=("G28", "AXIS_TWIST_COMPENSATION_CALIBRATE"),
        openneptune_macro="AXIS_TWIST_COMP_TUNE",
        duration_min=20.0,
        prerequisites=("probe_z_offset", "bed_screws_tilt"),
        capture_fields=("twist_compensation",),
    ),
    CalTestDef(
        id="rotation_distance",
        name="Extruder rotation distance",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.EXTRUSION,
        description="Mark filament, extrude 100mm, measure actual; update rotation_distance.",
        macro="FORGE_ROTATION_DISTANCE",
        klipper_commands=(
            "G28",
            "M83",
            "G1 E100 F60",
        ),
        duration_min=10.0,
        requires_filament=True,
        capture_fields=("commanded_mm", "actual_mm", "rotation_distance"),
        pass_criteria={"error_percent": 2.0},
    ),
    CalTestDef(
        id="input_shaper",
        name="Input shaper / resonance",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.MOTION,
        description="SHAPER_CALIBRATE with ADXL345 or Beacon/Eddy; enables high-speed G5.",
        macro="FORGE_SHAPER_CAL",
        klipper_commands=("SHAPER_CALIBRATE", "SAVE_CONFIG"),
        openneptune_macro="SHAPER_CALIBRATE",
        duration_min=20.0,
        requires_sensor="adxl345",
        capture_fields=("shaper_type_x", "shaper_freq_x", "shaper_type_y", "shaper_freq_y"),
        pass_criteria={"freq_stability_percent": 5.0},
    ),
    CalTestDef(
        id="mesh_golden",
        name="Golden bed mesh (precision)",
        category=CalCategory.ONE_TIME,
        phase=CalPhase.GEOMETRY,
        description="9×9 hot mesh after dual-bed soak; save as default profile.",
        macro="FORGE_MESH_PRECISION",
        klipper_commands=(
            "FORGE_HEAT_DUAL_BED BED=65",
            "FORGE_BED_SOAK MIN=6",
            "G28",
            "FORGE_MESH_PRECISION",
            "BED_MESH_PROFILE SAVE=default",
            "SAVE_CONFIG",
        ),
        openneptune_macro="AUTO_FULL_BED_LEVEL",
        duration_min=25.0,
        prerequisites=("probe_z_offset", "pid_bed_inner", "pid_bed_outer"),
        capture_fields=("peak_to_peak_mm", "point_count", "min_mm", "max_mm"),
        pass_criteria={"peak_to_peak_mm_max": 0.80, "preferred_mm_max": 0.40},
    ),
]

# ---------------------------------------------------------------------------
# PERIODIC (weekly, bed swap, nozzle change)
# ---------------------------------------------------------------------------

_PERIODIC: List[CalTestDef] = [
    CalTestDef(
        id="mesh_balanced",
        name="Session bed mesh (balanced)",
        category=CalCategory.PERIODIC,
        phase=CalPhase.GEOMETRY,
        description="7×7 hot mesh at print temp — session standard.",
        macro="FORGE_MESH_BALANCED",
        klipper_commands=("FORGE_HEAT_DUAL_BED", "FORGE_BED_SOAK MIN=3", "G28", "FORGE_MESH_BALANCED"),
        duration_min=8.0,
        capture_fields=("peak_to_peak_mm",),
        pass_criteria={"peak_to_peak_mm_max": 0.80},
    ),
    CalTestDef(
        id="dual_bed_soak",
        name="Dual-bed thermal soak",
        category=CalCategory.PERIODIC,
        phase=CalPhase.THERMAL,
        description="Equalize inner/outer bed zones before precision prints.",
        macro="FORGE_HEAT_DUAL_BED",
        klipper_commands=("FORGE_HEAT_DUAL_BED BED=65", "FORGE_BED_SOAK MIN=6"),
        duration_min=15.0,
        capture_fields=("inner_temp_c", "outer_temp_c", "max_delta_c"),
        pass_criteria={"max_delta_c": 3.0},
    ),
    CalTestDef(
        id="nozzle_check",
        name="Nozzle / abrasive preflight",
        category=CalCategory.PERIODIC,
        phase=CalPhase.PREFLIGHT,
        description="Verify nozzle type matches filament abrasive rating.",
        macro="FORGE_PREFLIGHT",
        duration_min=1.0,
        capture_fields=("nozzle_type", "material_sku", "preflight_ok"),
    ),
]

# ---------------------------------------------------------------------------
# FINE-TUNING (per material / session / environment)
# ---------------------------------------------------------------------------

_FINE_TUNE: List[CalTestDef] = [
    CalTestDef(
        id="z_offset_live",
        name="Live Z offset / baby steps",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.GEOMETRY,
        description="Fine first-layer squish via FORGE_BABY_UP/DOWN or SET_GCODE_OFFSET.",
        macro="FORGE_SET_Z_ADJUST",
        klipper_commands=("FORGE_Z_STATUS",),
        duration_min=5.0,
        capture_fields=("z_adjust_mm", "first_layer_quality"),
        pass_criteria={"continuous_lines": True, "no_scrape": True},
    ),
    CalTestDef(
        id="first_layer_squish",
        name="First layer squish panel",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.QUALITY,
        description="Print single-layer panel; tune Z until lines merge without scrape.",
        macro="FORGE_FIRST_LAYER_TEST",
        requires_filament=True,
        duration_min=15.0,
        prerequisites=("mesh_balanced", "z_offset_live"),
        capture_fields=("z_adjust_mm", "adhesion", "elephant_foot_mm"),
    ),
    CalTestDef(
        id="flow_rate",
        name="Flow rate (single wall)",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.EXTRUSION,
        description="Measure single-wall thickness vs line width; adjust flow multiplier.",
        macro="FORGE_FLOW_CAL",
        requires_filament=True,
        duration_min=20.0,
        capture_fields=("measured_wall_mm", "line_width_mm", "flow_percent"),
        pass_criteria={"flow_percent_min": 95.0, "flow_percent_max": 105.0},
    ),
    CalTestDef(
        id="pressure_advance",
        name="Pressure advance tower",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.EXTRUSION,
        description="TUNING_TOWER PA pattern; measure sharpest corner height.",
        macro="FORGE_PA_CAL",
        klipper_commands=(
            "SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=1 ACCEL=500",
            "TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE PARAMETER=ADVANCE START=0 FACTOR=.005",
        ),
        requires_filament=True,
        duration_min=25.0,
        capture_fields=("sharp_height_mm", "pressure_advance"),
        pass_criteria={"pa_range": [0.02, 0.12]},
    ),
    CalTestDef(
        id="temperature_tower",
        name="Temperature tower",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.THERMAL,
        description="Step nozzle temp per layer; pick best surface/bridging.",
        macro="FORGE_TEMP_TOWER",
        klipper_commands=(
            "TUNING_TOWER COMMAND=SET_HEATER_TEMPERATURE HEATER=extruder "
            "PARAMETER=TARGET START=200 STEP_DELTA=5 STEP_HEIGHT=5",
        ),
        requires_filament=True,
        duration_min=30.0,
        capture_fields=("best_layer_height_mm", "nozzle_temp_c"),
    ),
    CalTestDef(
        id="retraction_distance",
        name="Retraction tower",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.EXTRUSION,
        description="Tune retraction length for stringing vs gaps on HTPLA.",
        macro="FORGE_RETRACT_TOWER",
        requires_filament=True,
        duration_min=25.0,
        capture_fields=("clean_height_mm", "retract_mm"),
    ),
    CalTestDef(
        id="speed_accel",
        name="Speed / acceleration limits",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.MOTION,
        description="Stepwise accel/speed until ringing or quality fails; needs shaper.",
        macro="FORGE_SPEED_STEP",
        prerequisites=("input_shaper",),
        requires_filament=True,
        duration_min=30.0,
        capture_fields=("max_accel", "max_speed_mm_s", "ringing_ok"),
    ),
    CalTestDef(
        id="fan_tuning",
        name="Part cooling fan",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.QUALITY,
        description="Bridge/overhang test across fan speeds for HTPLA.",
        macro="FORGE_FAN_TUNE",
        requires_filament=True,
        duration_min=20.0,
        capture_fields=("fan_percent", "bridge_quality"),
    ),
    CalTestDef(
        id="mesh_fast",
        name="Fast mesh (production)",
        category=CalCategory.FINE_TUNE,
        phase=CalPhase.GEOMETRY,
        description="5×5 mesh or LOAD default — every-print path.",
        macro="FORGE_MESH_FAST",
        klipper_commands=("FORGE_MESH_SMART MODE=1",),
        duration_min=2.0,
        capture_fields=("peak_to_peak_mm",),
    ),
]

# ---------------------------------------------------------------------------
# GATE VERIFICATION (zero-trust evidence)
# ---------------------------------------------------------------------------

_GATE: List[CalTestDef] = [
    CalTestDef(
        id="dimensional_accuracy",
        name="G3 dimensional accuracy (100 mm bar)",
        category=CalCategory.GATE,
        phase=CalPhase.DIMENSIONAL,
        description="100 mm coupon; |error| ≤ 0.20 mm (aim 0.15).",
        macro="FORGE_PRINT_COUPON",
        requires_filament=True,
        duration_min=60.0,
        prerequisites=("mesh_balanced", "flow_rate", "pressure_advance"),
        capture_fields=("measured_mm", "nominal_mm", "error_mm", "print_time_s"),
        pass_criteria={"abs_error_mm_max": 0.20, "aim_mm_max": 0.15},
    ),
    CalTestDef(
        id="precision_replicate",
        name="G4 precision (3× replicate)",
        category=CalCategory.GATE,
        phase=CalPhase.DIMENSIONAL,
        description="Same G-code 3×; span ≤ 0.10 mm on 100 mm feature.",
        requires_filament=True,
        duration_min=180.0,
        prerequisites=("dimensional_accuracy",),
        capture_fields=("measurements_mm", "span_mm", "mean_error_mm"),
        pass_criteria={"span_mm_max": 0.10},
    ),
    CalTestDef(
        id="speed_regression",
        name="G5 speed vs T0 baseline",
        category=CalCategory.GATE,
        phase=CalPhase.QUALITY,
        description="≥25% faster than T0 while G3/G4 hold.",
        requires_filament=True,
        duration_min=45.0,
        prerequisites=("dimensional_accuracy", "precision_replicate"),
        capture_fields=("baseline_s", "trial_s", "improvement_percent", "dim_error_mm"),
        pass_criteria={"improvement_min_percent": 25.0, "abs_error_mm_max": 0.20},
    ),
    CalTestDef(
        id="anneal_dimensional",
        name="G6 anneal dimensional loop",
        category=CalCategory.GATE,
        phase=CalPhase.DIMENSIONAL,
        description="Pre/post anneal measure; post-anneal within band with compensation.",
        requires_filament=True,
        duration_min=240.0,
        prerequisites=("dimensional_accuracy",),
        capture_fields=("pre_anneal_mm", "post_anneal_mm", "shrink_percent"),
        pass_criteria={"post_abs_error_mm_max": 0.20},
    ),
    CalTestDef(
        id="reliability_soak",
        name="G7 reliability soak",
        category=CalCategory.GATE,
        phase=CalPhase.RELIABILITY,
        description="≥2 h idle/thermal; 0 MCU losses; log growth capped.",
        duration_min=120.0,
        capture_fields=("soak_hours", "mcu_losses", "log_growth_mb_per_day"),
        pass_criteria={"soak_hours_min": 2.0, "mcu_losses_max": 0},
    ),
]

CALIBRATION_CATALOG: Dict[str, CalTestDef] = {}
for _t in _ONE_TIME + _PERIODIC + _FINE_TUNE + _GATE:
    CALIBRATION_CATALOG[_t.id] = _t

ONE_TIME_SEQUENCE: List[str] = [t.id for t in _ONE_TIME]
FINE_TUNE_SEQUENCE: List[str] = [t.id for t in _FINE_TUNE]
FULL_CAMPAIGN_SEQUENCE: List[str] = [
    "pid_extruder",
    "pid_bed_inner",
    "pid_bed_outer",
    "probe_z_offset",
    "bed_screws_tilt",
    "mesh_golden",
    "rotation_distance",
    "input_shaper",
    "flow_rate",
    "pressure_advance",
    "dimensional_accuracy",
    "precision_replicate",
]


def get_calibration_test(test_id: str) -> Optional[CalTestDef]:
    return CALIBRATION_CATALOG.get(test_id)


# Backward-compatible alias (not test_* — pytest collects those)
test_by_id = get_calibration_test


def one_time_tests() -> List[CalTestDef]:
    return list(_ONE_TIME)


def fine_tune_tests() -> List[CalTestDef]:
    return list(_FINE_TUNE)


def gate_tests() -> List[CalTestDef]:
    return list(_GATE)


def periodic_tests() -> List[CalTestDef]:
    return list(_PERIODIC)


def tests_for_phase(phase: CalPhase) -> List[CalTestDef]:
    return [t for t in CALIBRATION_CATALOG.values() if t.phase == phase]


def calibration_tests_for_category(category: CalCategory) -> List[CalTestDef]:
    return [t for t in CALIBRATION_CATALOG.values() if t.category == category]


tests_for_category = calibration_tests_for_category
