from forgeos.vision.adaptive_state import AdaptiveState, ema
from forgeos.vision.dynamic_controller import DynamicController
from forgeos.vision.scorers.first_layer import score_first_layer_features
from forgeos.vision.telemetry_features import TelemetryFeatures, extract_telemetry


def test_ema_moves():
    assert abs(ema(0.0, 1.0, 0.5) - 0.5) < 1e-9


def test_extract_telemetry_flat_score():
    status = {
        "print_stats": {"state": "printing", "filename": "x.gcode"},
        "extruder": {"temperature": 214, "target": 214},
        "heater_bed": {"temperature": 65, "target": 65},
        "gcode_move": {
            "homing_origin": [0, 0, -0.48, 0],
            "gcode_position": [100, 100, 0.28, 0],
            "speed_factor": 1.0,
            "extrude_factor": 1.0,
        },
        "toolhead": {},
        "virtual_sdcard": {"progress": 0.05},
    }
    f = extract_telemetry(status, spacing_ratio=1.0, flow=1.0)
    assert f.printing
    assert f.first_layer_window
    assert f.flat_volume_score > 0.9
    assert abs(f.z_adjust_mm - (-0.48)) < 1e-6


def test_controller_suggests_without_arm():
    st = AdaptiveState(armed=False, mode="suggest")
    ctl = DynamicController(st)
    tele = TelemetryFeatures(
        ts=0,
        printing=True,
        print_state="printing",
        filename="t.gcode",
        progress=0.02,
        z_adjust_mm=-0.48,
        nozzle_c=214,
        nozzle_target_c=214,
        bed_c=65,
        bed_target_c=65,
        tool_z_mm=0.28,
        speed_factor=1.0,
        extrude_factor=1.0,
        heat_ready=True,
        first_layer_window=True,
        ridge_proxy_mm=0.0,
        flat_volume_score=1.0,
        thermal_track_score=1.0,
    )
    vis = score_first_layer_features(120, 80, 50, 0.7)  # ribbed
    tick = ctl.plan(tele, vision=vis, now=1000.0)
    assert tick.mode == "suggest"
    assert ctl.scripts_to_apply(tick) == []  # not armed
    assert any(a.kind == "gcode" for a in tick.actions)


def test_controller_armed_applies_one():
    st = AdaptiveState(armed=True, mode="armed", min_apply_interval_s=0.0)
    ctl = DynamicController(st)
    tele = TelemetryFeatures(
        ts=0,
        printing=True,
        print_state="printing",
        filename="t.gcode",
        progress=0.02,
        z_adjust_mm=-0.48,
        nozzle_c=214,
        nozzle_target_c=214,
        bed_c=65,
        bed_target_c=65,
        tool_z_mm=0.28,
        speed_factor=1.0,
        extrude_factor=1.0,
        heat_ready=True,
        first_layer_window=True,
        ridge_proxy_mm=0.0,
        flat_volume_score=0.5,
        thermal_track_score=1.0,
    )
    vis = score_first_layer_features(10, 0, 0, 0.05)  # empty → baby up
    tick = ctl.plan(tele, vision=vis, now=2000.0)
    scripts = ctl.scripts_to_apply(tick)
    assert scripts
    assert "BABY_UP" in scripts[0] or "FORGE" in scripts[0]


def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    st = AdaptiveState(z_adjust_mm=-0.48, flow=1.02, armed=True)
    st.observe_quality(flat_score=0.9, rib_score=0.1, coverage=0.8)
    st.save(p)
    st2 = AdaptiveState.load(p)
    assert abs(st2.z_adjust_mm - (-0.48)) < 1e-9
    assert st2.armed is True
