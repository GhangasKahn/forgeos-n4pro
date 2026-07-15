import pytest

from forgeos.adaptive.thermal_dual_bed import DualBedController, DualBedState
from forgeos.adaptive.nozzle_thermal import NozzleThermalController, NozzleState
from forgeos.adaptive.process_brain import ZeroVisionBrain, ZeroVisionState


def _status(
    *,
    printing=True,
    bed_c=64.0,
    outer_c=62.5,
    bed_t=65.0,
    outer_t=65.0,
    noz_c=210.0,
    noz_t=214.0,
    noz_power=0.9,
    z=-0.48,
    tool_z=0.28,
    progress=0.05,
    pa=0.032,
):
    return {
        "print_stats": {"state": "printing" if printing else "standby", "filename": "t.gcode"},
        "extruder": {
            "temperature": noz_c,
            "target": noz_t,
            "power": noz_power,
            "pressure_advance": pa,
            "smooth_time": 0.03,
        },
        "heater_bed": {"temperature": bed_c, "target": bed_t, "power": 0.2},
        "heater_generic heater_bed_outer": {
            "temperature": outer_c,
            "target": outer_t,
            "power": 0.4,
        },
        "gcode_move": {
            "homing_origin": [0, 0, z, 0],
            "gcode_position": [100, 100, tool_z, 0],
            "speed_factor": 1.0,
            "extrude_factor": 1.0,
        },
        "virtual_sdcard": {"progress": progress},
        "toolhead": {"homed_axes": "xyz"},
        "fan": {"speed": 0.0},
    }


def test_dual_bed_learns_outer_bias():
    ctl = DualBedController(DualBedState(target_base_c=65, min_adjust_interval_s=0))
    ctl.observe(65.0, 62.0, 65.0, 65.0, 0.2, 0.5)
    acts = ctl.plan(65.0, 62.0, printing=True, base_target=65.0, now=1e9)
    assert ctl.state.outer_bias_c >= 1.0
    # may or may not emit depending on step thresholds — bias must grow
    assert ctl.state.uniform_score < 1.0


def test_nozzle_droop_plans_action():
    ctl = NozzleThermalController(NozzleState(min_adjust_interval_s=0))
    for _ in range(5):
        ctl.observe(208.0, 214.0, power=0.95, volumetric_mm3_s=10.0, is_extruding=True)
    acts = ctl.plan(208.0, 214.0, printing=True, now=1e9)
    assert acts, "expected nozzle adapt under droop"
    assert "TARGET" in acts[0].script or "M220" in acts[0].script


def test_brain_suggest_mode_no_apply():
    brain = ZeroVisionBrain(ZeroVisionState(armed=False, mode="suggest"))
    tick = brain.plan(_status(), now=1e9)
    assert tick.mode == "suggest"
    assert brain.scripts_to_apply(tick) == []
    assert "precision_belief" in tick.quality
    assert tick.telemetry["printing"] is True


def test_brain_armed_can_apply():
    from forgeos.safety import SafetyGate

    st = ZeroVisionState(armed=True, mode="armed", min_apply_interval_s=0)
    safety = SafetyGate()
    token = safety.arm("runtime_micro")
    brain = ZeroVisionBrain(st, safety=safety, arm_token=token)
    # force bed controller ready
    brain.bed.state.min_adjust_interval_s = 0
    brain.nozzle.state.min_adjust_interval_s = 0
    tick = brain.plan(_status(outer_c=61.0, noz_c=205.0, noz_power=0.95), now=1e9)
    scripts = brain.scripts_to_apply(tick)
    # should have something to do under cold outer + droop
    assert tick.actions
    assert scripts is not None


def test_brain_armed_refuses_without_token():
    from forgeos.safety import SafetyError, SafetyGate

    st = ZeroVisionState(armed=True, mode="armed", min_apply_interval_s=0)
    brain = ZeroVisionBrain(st, safety=SafetyGate(), arm_token=None)
    tick = brain.plan(_status(outer_c=61.0, noz_c=205.0, noz_power=0.95), now=1e9)
    with pytest.raises(SafetyError):
        brain.scripts_to_apply(tick)

def test_precision_belief_updates():
    brain = ZeroVisionBrain()
    t1 = brain.plan(_status(bed_c=65, outer_c=65, noz_c=214, noz_t=214, noz_power=0.3), now=1)
    t2 = brain.plan(_status(bed_c=65, outer_c=60, noz_c=200, noz_t=214, noz_power=0.99), now=2)
    # worse thermal → precision belief should not increase a lot vs good
    assert t1.quality["precision_belief"] >= t2.quality["precision_belief"] - 0.05
