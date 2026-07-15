"""CNC precision / process capability tests."""

import pytest

from forgeos.precision import (
    PrecisionTier,
    get_band,
    process_capability,
    recommend_xy_scale,
    scale_correction,
)


def test_cnc_band_defaults():
    b = get_band(PrecisionTier.CNC)
    assert b.abs_error_max_mm == 0.10
    assert b.span_max_mm == 0.05
    assert b.mesh_p2p_max_mm == 0.25


def test_scale_correction():
    assert scale_correction(100.0, 99.5) == pytest.approx(100.0 / 99.5)


def test_process_capability_cnc_pass():
    cap = process_capability([100.01, 99.99, 100.00], nominal_mm=100.0)
    assert cap.passed
    assert cap.span_mm <= 0.05
    assert cap.cpk is not None and cap.cpk >= 1.0


def test_process_capability_cnc_fail_span():
    cap = process_capability([100.0, 100.12, 99.95], nominal_mm=100.0)
    assert not cap.passed


def test_recommend_xy_scale():
    s = recommend_xy_scale([99.8, 99.9, 99.85], 100.0)
    assert s > 1.0
