"""Self-contained calibration G-code patterns for Neptune 4 Pro (225 mm bed).

Generates printable coupons without requiring a slicer for FLOW / PA / first-layer /
extrusion mark tests. Host uploads or pastes into virtual SD.
"""

from __future__ import annotations

import math
from typing import List, Optional


BED_SIZE = 225.0
FILAMENT_D_MM = 1.75


def _e(dist: float, line_w: float, layer_h: float, flow: float = 1.0) -> float:
    fil_area = math.pi * (FILAMENT_D_MM / 2.0) ** 2
    return (line_w * layer_h * dist * flow) / fil_area


def _hdr(title: str) -> List[str]:
    return [
        "; ForgeOS calibration pattern — %s" % title,
        "; Printer: Elegoo Neptune 4 Pro (OpenNeptune / ForgeOS)",
        "M83",
        "G90",
        "G92 E0",
    ]


def gcode_print_start(bed: float = 65.0, nozzle: float = 214.0, soak: float = 5.0) -> List[str]:
    return [
        "FORGE_PRINT_START_ENV BED=%.2f EXTRUDER=%.2f SOAK=%.2f" % (bed, nozzle, soak),
    ]


def gcode_print_end() -> List[str]:
    return ["FORGE_PRINT_END_ENV"]


def generate_extrude_cal_script(
    commanded_mm: float = 100.0,
    feed_mm_min: float = 60.0,
    hotend_c: float = 214.0,
) -> str:
    """Heat + slow extrusion for rotation_distance measurement (no bed move required)."""
    lines = [
        "; FORGE_EXTRUDE_CAL — mark filament at 120 mm above entry; command %.0f mm" % commanded_mm,
        "M83",
        "G92 E0",
        "M104 S%.0f" % hotend_c,
        "TEMPERATURE_WAIT SENSOR=extruder MINIMUM=%.0f MAXIMUM=%.0f" % (hotend_c - 2, hotend_c + 5),
        "G1 E%.2f F%.0f" % (commanded_mm, feed_mm_min),
        "M104 S0",
        'RESPOND MSG="Measure remaining mark distance; actual = 120 - leftover"',
    ]
    return "\n".join(lines) + "\n"


def generate_flow_shell(
    *,
    bed: float = 65.0,
    nozzle: float = 214.0,
    soak: float = 3.0,
    size_mm: float = 40.0,
    height_mm: float = 12.0,
    layer_h: float = 0.20,
    line_w: float = 0.44,
    perimeters: int = 1,
    flow: float = 1.0,
    speed_mm_s: float = 60.0,
    pa: float = 0.0,
) -> str:
    """Hollow single-wall cube for flow calibration (Klippain / Orca style)."""
    x0 = (BED_SIZE - size_mm) / 2.0
    y0 = (BED_SIZE - size_mm) / 2.0
    x1 = x0 + size_mm
    y1 = y0 + size_mm
    layers = max(1, int(round(height_mm / layer_h)))
    expected = line_w * perimeters
    L: List[str] = []
    a = L.append
    a("; FLOW shell — expected wall = %.3f mm (%d × %.3f)" % (expected, perimeters, line_w))
    a("; After print: FORGE_COMPUTE_FLOW MEASURED=... LINE_W=%.3f PERIMS=%d" % (line_w, perimeters))
    L.extend(gcode_print_start(bed, nozzle, soak))
    L.extend(_hdr("flow_shell"))
    a("SET_PRESSURE_ADVANCE ADVANCE=%.4f" % pa)
    a("M221 S%d" % int(round(flow * 100)))
    a("M106 S0")
    spd = int(speed_mm_s * 60)
    z = layer_h
    # first layer slower
    a("G0 Z%.3f F600" % z)
    a("G0 X%.3f Y%.3f F9000" % (x0, y0))
    for i in range(layers):
        z = round(layer_h * (i + 1), 3)
        this_spd = int(20 * 60) if i == 0 else spd
        a("G1 Z%.3f F600" % z)
        for _p in range(perimeters):
            inset = _p * line_w
            xa, ya = x0 + inset, y0 + inset
            xb, yb = x1 - inset, y1 - inset
            side = xb - xa
            e_side = _e(side, line_w, layer_h, flow)
            a("G1 X%.3f Y%.3f F9000" % (xa, ya))
            a("G1 X%.3f Y%.3f E%.5f F%d" % (xb, ya, e_side, this_spd))
            a("G1 X%.3f Y%.3f E%.5f F%d" % (xb, yb, e_side, this_spd))
            a("G1 X%.3f Y%.3f E%.5f F%d" % (xa, yb, e_side, this_spd))
            a("G1 X%.3f Y%.3f E%.5f F%d" % (xa, ya, e_side, this_spd))
        a("G92 E0")
    L.extend(gcode_print_end())
    return "\n".join(L) + "\n"


def generate_pa_tower(
    *,
    bed: float = 65.0,
    nozzle: float = 214.0,
    soak: float = 3.0,
    size_mm: float = 60.0,
    height_mm: float = 50.0,
    layer_h: float = 0.20,
    line_w: float = 0.48,
    start_pa: float = 0.0,
    factor: float = 0.005,
    speed_mm_s: float = 100.0,
) -> str:
    """Single-wall square tower + TUNING_TOWER for pressure advance (direct drive)."""
    x0 = (BED_SIZE - size_mm) / 2.0
    y0 = (BED_SIZE - size_mm) / 2.0
    x1 = x0 + size_mm
    y1 = y0 + size_mm
    layers = max(1, int(round(height_mm / layer_h)))
    L: List[str] = []
    a = L.append
    a("; PA tower — measure height of best corners; PA = %.3f + height * %.4f" % (start_pa, factor))
    a("; Then: FORGE_COMPUTE_PA HEIGHT=... START=%.3f FACTOR=%.4f" % (start_pa, factor))
    L.extend(gcode_print_start(bed, nozzle, soak))
    L.extend(_hdr("pa_tower"))
    a("SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=1 ACCEL=500")
    a(
        "TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE PARAMETER=ADVANCE START=%.4f FACTOR=%.5f"
        % (start_pa, factor)
    )
    a("M221 S100")
    a("M106 S0")
    spd = int(speed_mm_s * 60)
    for i in range(layers):
        z = round(layer_h * (i + 1), 3)
        this_spd = int(25 * 60) if i == 0 else spd
        a("G1 Z%.3f F600" % z)
        side = size_mm
        e_side = _e(side, line_w, layer_h, 1.0)
        a("G1 X%.3f Y%.3f F9000" % (x0, y0))
        a("G1 X%.3f Y%.3f E%.5f F%d" % (x1, y0, e_side, this_spd))
        a("G1 X%.3f Y%.3f E%.5f F%d" % (x1, y1, e_side, this_spd))
        a("G1 X%.3f Y%.3f E%.5f F%d" % (x0, y1, e_side, this_spd))
        a("G1 X%.3f Y%.3f E%.5f F%d" % (x0, y0, e_side, this_spd))
        a("G92 E0")
    a("SET_PRESSURE_ADVANCE ADVANCE=0")
    L.extend(gcode_print_end())
    return "\n".join(L) + "\n"


def generate_pa_fine_tower(
    seed_pa: float = 0.030,
    band: float = 0.010,
    factor: float = 0.002,
    **kwargs,
) -> str:
    """Narrow PA tower centered on seed for fine-tune."""
    start = max(0.0, seed_pa - band)
    # height so end ≈ seed+band: height = 2*band/factor
    height = max(20.0, (2.0 * band) / factor)
    return generate_pa_tower(start_pa=start, factor=factor, height_mm=height, **kwargs)


def generate_first_layer_patch(
    *,
    bed: float = 65.0,
    nozzle: float = 214.0,
    soak: float = 5.0,
    size_mm: float = 80.0,
    layer_h: float = 0.28,
    line_w: float = 0.44,
    flow: float = 1.0,
    speed_mm_s: float = 30.0,
    pa: float = 0.030,
) -> str:
    """Machine-flat first-layer square (s=w, volume balanced)."""
    x0 = (BED_SIZE - size_mm) / 2.0
    y0 = (BED_SIZE - size_mm) / 2.0
    spacing = line_w  # machine-flat rule
    rows = int(size_mm / spacing)
    L: List[str] = []
    a = L.append
    a("; First-layer patch — machine-flat s=w flow=%.2f — baby-step Z then SAVE" % flow)
    L.extend(gcode_print_start(bed, nozzle, soak))
    L.extend(_hdr("first_layer_patch"))
    a("SET_PRESSURE_ADVANCE ADVANCE=%.4f" % pa)
    a("FORGE_FLAT_SURFACE_MODE ROLE=first")
    a("M221 S%d" % int(round(flow * 100)))
    a("M106 S0")
    a("FORGE_PURGE")
    a("G0 Z%.3f F600" % layer_h)
    spd = int(speed_mm_s * 60)
    for i in range(rows):
        y = y0 + i * spacing
        e = _e(size_mm, line_w, layer_h, flow)
        if i % 2 == 0:
            a("G0 X%.3f Y%.3f F9000" % (x0, y))
            a("G1 X%.3f Y%.3f E%.5f F%d" % (x0 + size_mm, y, e, spd))
        else:
            a("G0 X%.3f Y%.3f F9000" % (x0 + size_mm, y))
            a("G1 X%.3f Y%.3f E%.5f F%d" % (x0, y, e, spd))
        a("G92 E0")
    a('RESPOND MSG="Inspect squish; FORGE_BABY_UP/DOWN; Z_OFFSET_APPLY_PROBE then SAVE_CONFIG"')
    L.extend(gcode_print_end())
    return "\n".join(L) + "\n"


def generate_retract_tower_hint() -> str:
    """Guidance gcode comments — retract towers usually come from Orca; we document macros."""
    return "\n".join(
        [
            "; Retract calibration — use Orca stringing tower with firmware retract OFF while tuning.",
            "; Seed (N4 Pro geared + Brozzl plated copper + HTPLA):",
            ";   FORGE_SET_RETRACT LENGTH=1.20 SPEED=40 WIPE=1.4 ZHOP=0.25",
            "; After tuning, re-enable firmware retract and set slicer overrides to match.",
            "; Z-hop OpenNeptune default band: 0.3–0.6 mm; ForgeOS shop seed 0.25 mm.",
        ]
    ) + "\n"


def write_pattern(path: str, content: str) -> str:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)
