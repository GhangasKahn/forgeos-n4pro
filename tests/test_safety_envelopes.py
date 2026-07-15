import pytest

from forgeos.safety import SafetyError, SafetyGate


def test_arming_required():
    g = SafetyGate()
    with pytest.raises(SafetyError):
        g.require_armed("autotune", "nope")
    tok = g.arm("autotune", ttl_s=60)
    g.require_armed("autotune", tok)
    g.disarm("autotune")
    with pytest.raises(SafetyError):
        g.require_armed("autotune", tok)


def test_clamps():
    g = SafetyGate()
    assert g.clamp_velocity(999, role="outer_wall") == 300
    assert g.clamp_velocity(999, role="travel") == 300
    assert g.clamp_accel(50000) == 5000
    assert g.clamp_nozzle_temp(300) == 240
    assert g.clamp_z_offset_delta(0.5) == 0.02


def test_preflight_cf_nozzle():
    g = SafetyGate()
    with pytest.raises(SafetyError):
        g.preflight_nozzle(True, "brass", 0.4, 0.5)
    g.preflight_nozzle(True, "hardened", 0.6, 0.5)


def test_dim_gate():
    g = SafetyGate()
    g.assert_dim_gate(0.10)
    with pytest.raises(SafetyError):
        g.assert_dim_gate(0.25)
