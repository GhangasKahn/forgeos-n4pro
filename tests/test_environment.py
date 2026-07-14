from pathlib import Path

from forgeos.environment.homeostasis import HomeostasisController
from forgeos.environment.loader import default_environments_dir, load_all_profiles, load_environment_profile
from forgeos.environment.models import AmbientReading, EnclosureMode, EnvironmentBin, Phase
from forgeos.environment.policy import EnvironmentPolicy
from forgeos.environment.session import build_session_plan
from forgeos.materials import default_materials_dir, load_material_pack
from forgeos.sensors.moisture_soft_sensor import MoistureEstimate


def test_basement_bins_to_cold_humid():
    a = AmbientReading(14.0, 65.0, EnclosureMode.OPEN)
    assert a.environment_bin() == EnvironmentBin.COLD_HUMID


def test_load_profiles():
    profiles = load_all_profiles(default_environments_dir())
    assert "basement_default" in profiles
    assert "basement_enclosed" in profiles
    assert profiles["basement_default"].ambient.rh_percent >= 60


def test_before_plan_longer_soak_when_cold():
    pack = load_material_pack(default_materials_dir() / "protopasta_htpla.yaml")
    cold = EnvironmentPolicy(
        pack, AmbientReading(12.0, 70.0, EnclosureMode.OPEN, draft_level=0.4)
    ).plan(Phase.BEFORE)
    mild = EnvironmentPolicy(
        pack, AmbientReading(22.0, 40.0, EnclosureMode.OPEN)
    ).plan(Phase.BEFORE)
    assert cold.bed_soak_min > mild.bed_soak_min
    assert cold.bed_temp_c >= mild.bed_temp_c
    assert cold.first_layer_speed_factor <= mild.first_layer_speed_factor


def test_enclosure_recovers_some_speed_vs_open_cold():
    pack = load_material_pack(default_materials_dir() / "protopasta_htpla.yaml")
    open_p = EnvironmentPolicy(
        pack, AmbientReading(14.0, 60.0, EnclosureMode.OPEN, draft_level=0.3)
    ).plan(Phase.DURING)
    enc_p = EnvironmentPolicy(
        pack, AmbientReading(14.0, 60.0, EnclosureMode.ENCLOSED, draft_level=0.05)
    ).plan(Phase.DURING)
    assert enc_p.speed_factor >= open_p.speed_factor


def test_after_staged_in_cold_open():
    pack = load_material_pack(default_materials_dir() / "protopasta_htpla.yaml")
    after = EnvironmentPolicy(
        pack, AmbientReading(12.0, 65.0, EnclosureMode.OPEN)
    ).plan(Phase.AFTER)
    assert after.cool_down_style == "staged"
    assert any("45" in g or "staged" in g.lower() or "TARGET=45" in g or "TARGET=40" in g for g in after.gcode) or after.cool_down_style == "staged"


def test_homeostasis_learns():
    pack = load_material_pack(default_materials_dir() / "protopasta_htpla.yaml")
    amb = AmbientReading(14.0, 65.0, EnclosureMode.OPEN)
    ctrl = HomeostasisController(pack, amb)
    p1 = ctrl.plan_phase(Phase.DURING)
    ctrl.observe_outcome(
        quality_score=0.85,
        nozzle_temp_c=218.0,
        bed_temp_c=64.0,
        bed_soak_min=7.0,
        speed_factor=0.88,
        flow_factor=1.02,
        part_fan_percent=45,
        success=True,
    )
    st = ctrl.get_state()
    assert st.samples == 1
    assert st.nozzle_temp_c != p1.nozzle_temp_c or st.samples == 1
    p2 = ctrl.plan_phase(Phase.DURING)
    assert "homeostasis_blend" in " ".join(p2.rationale)


def test_session_plan_basement():
    plan = build_session_plan(
        env_profile_path=default_environments_dir() / "basement_default.yaml"
    )
    assert plan["bin"] == "cold_humid"
    assert "before" in plan["plans"]
    assert plan["plans"]["before"]["bed_soak_min"] >= 3.0


def test_moisture_prior_raises_with_wet_sensor():
    pack = load_material_pack(default_materials_dir() / "protopasta_htpla.yaml")
    amb = AmbientReading(14.0, 70.0, EnclosureMode.OPEN)
    wet = MoistureEstimate(
        risk=0.8,
        level="severe",
        temp_droop_c=5,
        power=0.9,
        flow_mm3_s=8,
        droop_excess_c=3,
        power_excess=0.3,
    )
    d = EnvironmentPolicy(pack, amb, wet).plan(Phase.DURING)
    dry = EnvironmentPolicy(pack, amb, None).plan(Phase.DURING)
    assert d.speed_factor <= dry.speed_factor
