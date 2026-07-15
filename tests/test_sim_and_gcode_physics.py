"""Militant tests for digital twin + G-code physics."""

from __future__ import annotations

import time

import pytest

from forgeos.gcode_physics import validate_gcode
from forgeos.moonraker_client import MoonrakerClient
from forgeos.sim.moonraker_twin import reset_state, serve_background


@pytest.fixture()
def twin():
    reset_state(z_adjust_mm=-0.480)
    httpd, _t = serve_background("127.0.0.1", 27125)
    time.sleep(0.05)
    client = MoonrakerClient("127.0.0.1", 27125, timeout_s=3.0)
    yield client
    httpd.shutdown()


def test_twin_sim_flag(twin):
    info = twin.printer_info()["result"]
    assert info["sim"] is True
    assert twin.is_ready()


def test_twin_dual_bed_heat_and_mesh(twin):
    twin.gcode("SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=65")
    twin.gcode("SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=65")
    twin.gcode("G28")
    twin.gcode("BED_MESH_CALIBRATE")
    st = twin.objects_query(
        ["heater_bed", "heater_generic heater_bed_outer", "bed_mesh", "toolhead"]
    )["result"]["status"]
    assert st["heater_bed"]["temperature"] >= 40
    assert st["toolhead"]["homed_axes"] == "xyz"
    matrix = st["bed_mesh"]["probed_matrix"]
    assert len(matrix) >= 5
    vals = [v for r in matrix for v in r]
    p2p = max(vals) - min(vals)
    assert p2p <= 0.25 + 1e-6


def test_gcode_physics_pass():
    g = """
G90
M83
M104 S215
M140 S65
G0 Z0.28 F300
G0 X100 Y100 F6000
G1 X120 Y100 E0.5 F1200
G1 X120 Y120 E0.5
"""
    r = validate_gcode(g)
    assert r.passed, r.as_dict()
    assert r.extrusion_moves >= 2


def test_gcode_physics_fail_cold_extrude_z():
    g = """
G90
M83
G0 Z0.01
G1 X10 Y10 E1 F600
"""
    r = validate_gcode(g)
    assert not r.passed
    assert any(i.code == "z_too_low" for i in r.issues)


def test_gcode_physics_fail_hot_nozzle():
    g = """
M104 S350
G90
M83
G0 Z0.28
G1 X10 Y10 E0.2
"""
    r = validate_gcode(g)
    assert not r.passed
    assert any(i.code == "nozzle_temp" for i in r.issues)
