import pytest

from forgeos.stack_profile import StackError, compose_stack


def test_htpla_pex_brozzl_stack():
    s = compose_stack(
        filament_sku="protopasta_htpla",
        surface_sku="whambam_pex",
        nozzle_sku="brozzl_n4pro",
        ambient_temp_c=14.0,
        z_adjust_seed=-0.10,
    )
    assert s.bed_c == 65
    assert 210 <= s.nozzle_c <= 220
    assert s.soak_min >= 4.0
    assert s.first_layer_speed_mm_s == pytest.approx(28.5)
    assert s.first_layer_height_mm == pytest.approx(0.28)
    assert s.line_width_mm == pytest.approx(0.44)
    assert s.first_layer_flow == pytest.approx(1.0)
    assert s.brim is True
    assert s.glue is False
    assert s.nozzle_type_token == "brozzl_plated_copper"
    assert s.nozzle_c <= 215  # plated copper cooler bias
    assert s.retract_mm >= 1.15
    assert "FORGE_SET_SURFACE" in s.gcode_env_commands()[0]


def test_cf_rejects_brozzl():
    with pytest.raises(StackError):
        compose_stack(
            filament_sku="protopasta_htpla_cf",
            surface_sku="whambam_pex",
            nozzle_sku="brozzl_n4pro",
        )
