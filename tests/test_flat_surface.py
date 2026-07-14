from forgeos.flat_surface import (
    balance_flow_for_spacing,
    evaluate_geometry,
    machine_flat_pack,
    max_speed_for_q,
    residual_ridge_proxy_mm,
    spacing_for_flow,
)


def test_perfect_balance_zero_ridge():
    w, s, h, f = 0.44, 0.44, 0.2, 1.0
    assert abs(balance_flow_for_spacing(w, s) - 1.0) < 1e-9
    assert residual_ridge_proxy_mm(w, h, s, f) < 1e-9


def test_pile_up_has_ridge():
    # old bad pack: spacing 0.84*w with flow 1.14 still not perfect, but s<w piles
    w = 0.58
    s = 0.58 * 0.84
    h = 0.28
    # flow=1 with s<w overfills cell
    r = residual_ridge_proxy_mm(w, h, s, 1.0)
    assert r > 0.05


def test_machine_flat_pack_nail_ok():
    pack = machine_flat_pack()
    for name, geo in pack.items():
        rep = evaluate_geometry(geo)
        assert rep.nail_ok, (name, rep)
        assert rep.speed_ok, (name, rep)
        assert geo.monotonic
        assert abs(geo.spacing_mm - geo.line_width_mm) < 1e-9
        assert abs(geo.flow - 1.0) < 1e-9


def test_q_clamp_limits_speed():
    # absurd requested speed must clamp
    vmax = max_speed_for_q(0.44, 0.2, 1.0, 12.0)
    assert vmax < 200
    pack = machine_flat_pack(solid_speed_mm_s=500.0)
    assert pack["solid"].speed_mm_s <= vmax * 0.92 + 1e-6


def test_spacing_flow_inverse():
    assert abs(spacing_for_flow(0.44, 1.0) - 0.44) < 1e-9
    assert abs(balance_flow_for_spacing(0.44, 0.44) - 1.0) < 1e-9
