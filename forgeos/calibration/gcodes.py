"""G-code snippets for calibration patterns (Neptune 4 Pro 225×225 bed)."""

from __future__ import annotations

import math
from typing import List, Optional


def _filament_e(dist_mm: float, line_w: float, layer_h: float, flow: float = 1.0) -> float:
    fil_area = math.pi * (1.75 / 2.0) ** 2
    return (line_w * layer_h * dist_mm * flow) / fil_area


def gcode_pa_tower_prep(
    start_pa: float = 0.0,
    factor: float = 0.005,
    bed_c: float = 65.0,
    nozzle_c: float = 215.0,
) -> List[str]:
    """Prepend G-code for Klipper PA tuning tower."""
    return [
        "; ForgeOS PA tower prep",
        "M140 S%.0f" % bed_c,
        "M104 S%.0f" % nozzle_c,
        "G28",
        "G90",
        "M83",
        "SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=1 ACCEL=500",
        "TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE PARAMETER=ADVANCE START=%.3f FACTOR=%.3f"
        % (start_pa, factor),
    ]


def gcode_temp_tower_prep(
    start_c: float = 200.0,
    step_c: float = 5.0,
    step_h: float = 5.0,
    bed_c: float = 65.0,
) -> List[str]:
    return [
        "; ForgeOS temperature tower prep",
        "M140 S%.0f" % bed_c,
        "G28",
        "G90",
        "M83",
        "TUNING_TOWER COMMAND=SET_HEATER_TEMPERATURE HEATER=extruder "
        "PARAMETER=TARGET START=%.0f STEP_DELTA=%.0f STEP_HEIGHT=%.0f"
        % (start_c, step_c, step_h),
    ]


def gcode_single_wall_cube(
    size_mm: float = 20.0,
    layer_h: float = 0.2,
    line_w: float = 0.44,
    speed_mm_s: float = 30.0,
    bed_c: float = 65.0,
    nozzle_c: float = 215.0,
    z_center: bool = True,
) -> str:
    """Generate minimal single-wall hollow cube for flow calibration."""
    bed = 225.0
    x0 = (bed - size_mm) / 2.0
    y0 = (bed - size_mm) / 2.0
    x1 = x0 + size_mm
    y1 = y0 + size_mm
    spd = int(speed_mm_s * 60)
    layers = max(1, int(round(10.0 / layer_h)))
    lines: List[str] = [
        "; ForgeOS single-wall flow cube %.0f mm" % size_mm,
        "M140 S%.0f" % bed_c,
        "M104 S%.0f" % nozzle_c,
        "G28",
        "G90",
        "M83",
        "M109 S%.0f" % nozzle_c,
        "M190 S%.0f" % bed_c,
    ]
    z = layer_h
    for layer in range(layers):
        if layer == 0:
            z = layer_h
        e_wall = _filament_e(size_mm, line_w, layer_h)
        lines.append("G0 Z%.3f F300" % z)
        lines.append("G0 X%.3f Y%.3f F6000" % (x0, y0))
        lines.append("G1 X%.3f Y%.3f E%.5f F%d" % (x1, y0, e_wall, spd))
        lines.append("G1 X%.3f Y%.3f E%.5f" % (x1, y1, e_wall))
        lines.append("G1 X%.3f Y%.3f E%.5f" % (x0, y1, e_wall))
        lines.append("G1 X%.3f Y%.3f E%.5f" % (x0, y0, e_wall))
        z += layer_h
    lines.append("M104 S0")
    lines.append("M140 S0")
    return "\n".join(lines) + "\n"


def gcode_first_layer_panel(
    width_mm: float = 40.0,
    depth_mm: float = 40.0,
    line_w: float = 0.44,
    layer_h: float = 0.28,
    speed_mm_s: float = 18.0,
    bed_c: float = 65.0,
    nozzle_c: float = 215.0,
) -> str:
    """Single-layer infill panel for Z squish tuning."""
    bed = 225.0
    x0 = (bed - width_mm) / 2.0
    y0 = (bed - depth_mm) / 2.0
    x1 = x0 + width_mm
    y1 = y0 + depth_mm
    spd = int(speed_mm_s * 60)
    spacing = line_w
    lines: List[str] = [
        "; ForgeOS first-layer squish panel",
        "M140 S%.0f" % bed_c,
        "M104 S%.0f" % nozzle_c,
        "G28",
        "G90",
        "M83",
        "M109 S%.0f" % nozzle_c,
        "M190 S%.0f" % bed_c,
        "G0 Z%.3f F300" % layer_h,
    ]
    y = y0
    flip = False
    e_line = _filament_e(width_mm, line_w, layer_h)
    while y <= y1 + 1e-6:
        if not flip:
            lines.append("G0 X%.3f Y%.3f F6000" % (x0, y))
            lines.append("G1 X%.3f Y%.3f E%.5f F%d" % (x1, y, e_line, spd))
        else:
            lines.append("G0 X%.3f Y%.3f F6000" % (x1, y))
            lines.append("G1 X%.3f Y%.3f E%.5f F%d" % (x0, y, e_line, spd))
        y += spacing
        flip = not flip
    lines.append("M104 S0")
    lines.append("M140 S0")
    return "\n".join(lines) + "\n"


def gcode_rotation_distance_test(extrude_mm: float = 100.0) -> List[str]:
    """Commands for rotation distance measurement (operator marks filament)."""
    return [
        "; Mark filament 120mm above extruder entry, extrude %.0f mm, re-measure" % extrude_mm,
        "G28",
        "M83",
        "G1 E%.1f F60" % extrude_mm,
        "; actual_mm = 120 - remaining_mark_distance",
        "; new_rotation = old_rotation * (commanded / actual)",
    ]


def rotation_distance_from_measurement(
    old_rotation: float,
    commanded_mm: float,
    actual_mm: float,
) -> float:
    if actual_mm <= 0:
        raise ValueError("actual_mm must be positive")
    return old_rotation * (commanded_mm / actual_mm)


def gcode_retraction_tower_prep(
    start_mm: float = 0.5,
    step_mm: float = 0.5,
) -> List[str]:
    return [
        "; Retraction tower — slice with tuning tower or use Orca pattern",
        "SET_RETRACTION RETRACT_LENGTH=%.2f" % start_mm,
        "; increment %.2f mm per layer in slicer" % step_mm,
    ]
