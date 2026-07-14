#!/usr/bin/env python3
"""Machine-flat coupon — ZERO IRONING, monotonic solids, Q-limited speeds.

Prints:
  - Layer 0: first-layer pack (adhesion speed, fan 0)
  - Layers 1..N: solid pack (high speed)
  - Last layer: top_solid pack (slightly slower, more fan)

Geometry: spacing = line_width, flow = 1.0, monotonic rows only.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.extrusion_motion import (  # noqa: E402
    HTPLA_BROZZL,
    gcode_travel_unretract,
    gcode_wipe_retract,
)
from forgeos.flat_surface import (  # noqa: E402
    e_for_distance,
    evaluate_geometry,
    gcode_set_motion_for_flat,
    machine_flat_pack,
    monotonic_row_ys,
)


def emit_monotonic_rect(
    a,
    x0,
    y0,
    x1,
    y1,
    z,
    geo,
    profile,
    state,
):
    """Fill rectangle with monotonic (+X) extrusion rows."""
    cx, cy, last_dx, last_dy = state
    spd = int(geo.speed_mm_s * 60)
    ys = monotonic_row_ys(y0, y1, geo.spacing_mm, geo.line_width_mm)
    x_left = x0 + geo.line_width_mm * 0.5
    x_right = x1 - geo.line_width_mm * 0.5
    for yi, y in enumerate(ys):
        # always left → right (monotonic)
        tx, ex = x_left, x_right
        for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "row"):
            a(line)
        for line in gcode_travel_unretract(tx, y, z, profile):
            a(line)
        dist = abs(ex - tx)
        a(
            "G1 X%.4f Y%.4f E%.5f F%d"
            % (ex, y, e_for_distance(dist, geo), spd)
        )
        last_dx, last_dy = ex - tx, 0.0
        cx, cy = ex, y
    return cx, cy, last_dx, last_dy


def emit_walls(a, x0, y0, x1, y1, z, geo, profile, state, loops=2):
    cx, cy, last_dx, last_dy = state
    spd = int(geo.speed_mm_s * 60)
    for i in range(loops):
        inset = (i + 0.5) * geo.spacing_mm
        xa, ya = x0 + inset, y0 + inset
        xb, yb = x1 - inset, y1 - inset
        if xb <= xa or yb <= ya:
            break
        for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "wall"):
            a(line)
        for line in gcode_travel_unretract(xa, ya, z, profile):
            a(line)
        cx, cy = xa, ya
        for nx, ny in [(xb, ya), (xb, yb), (xa, yb), (xa, ya)]:
            dist = math.hypot(nx - cx, ny - cy)
            a(
                "G1 X%.4f Y%.4f E%.5f F%d"
                % (nx, ny, e_for_distance(dist, geo), spd)
            )
            last_dx, last_dy = nx - cx, ny - cy
            cx, cy = nx, ny
    return cx, cy, last_dx, last_dy


def gen(bed=65.0, nozzle=214.0, soak=3.0, size=50.0, solid_layers=4) -> str:
    pack = machine_flat_pack()
    first = pack["first_layer"]
    solid = pack["solid"]
    top = pack["top_solid"]
    profile = HTPLA_BROZZL

    # reports in header
    reps = {k: evaluate_geometry(v) for k, v in pack.items()}

    x0 = (225.0 - size) / 2.0
    y0 = (225.0 - size) / 2.0
    x1, y1 = x0 + size, y0 + size

    L = []
    a = L.append
    a("; ForgeOS MACHINE-FLAT COUPON — ZERO IRONING")
    a("; Monotonic solids | spacing=line_w | flow=1.0 | Q-limited speeds")
    for name, r in reps.items():
        g = pack[name]
        a(
            "; %s: w=%.3f s=%.3f h=%.3f f=%.3f v=%.1f Q=%.2f nail_ok=%s ridge≈%.4f"
            % (
                name,
                g.line_width_mm,
                g.spacing_mm,
                g.layer_height_mm,
                g.flow,
                g.speed_mm_s,
                r.volumetric_mm3_s,
                r.nail_ok,
                r.residual_ridge_proxy_mm,
            )
        )
    a("")
    a("FORGE_PRINT_START_ENV BED=%.2f EXTRUDER=%.2f SOAK=%.2f" % (bed, nozzle, soak))
    a("M83")
    a("G90")
    a("G92 E0")
    a("FORGE_FLAT_SET LINE_W=%.3f FLOW=%.3f PA=%.4f Q_MAX=12.0" % (first.line_width_mm, first.flow, first.pressure_advance))
    a("FORGE_PURGE X=15 Y=12 LEN=100 E=12 Z=%.2f" % (first.layer_height_mm + 0.02))

    state = (x0, y0, 1.0, 0.0)
    z = first.layer_height_mm

    # --- first layer ---
    a("")
    a("; === FIRST LAYER (adhesion, flat volume) ===")
    a("FORGE_FLAT_SURFACE_MODE ROLE=first")
    for line in gcode_set_motion_for_flat(first):
        a(line)
    a("G0 Z%.3f F600" % z)
    state = emit_walls(a, x0, y0, x1, y1, z, first, profile, state, loops=2)
    inset = 2 * first.spacing_mm
    state = emit_monotonic_rect(
        a, x0 + inset, y0 + inset, x1 - inset, y1 - inset, z, first, profile, state
    )

    # --- solid layers ---
    for i in range(1, solid_layers):
        z = first.layer_height_mm + i * solid.layer_height_mm
        is_top = i == solid_layers - 1
        geo = top if is_top else solid
        role = "top" if is_top else "solid"
        a("")
        a("; === LAYER %d Z=%.3f role=%s v=%.1f ===" % (i, z, role, geo.speed_mm_s))
        a("FORGE_FLAT_SURFACE_MODE ROLE=%s" % role)
        for line in gcode_set_motion_for_flat(geo):
            a(line)
        state = emit_walls(a, x0, y0, x1, y1, z, geo, profile, state, loops=2)
        inset = 2 * geo.spacing_mm
        state = emit_monotonic_rect(
            a, x0 + inset, y0 + inset, x1 - inset, y1 - inset, z, geo, profile, state
        )

    cx, cy, last_dx, last_dy = state
    for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "done"):
        a(line)
    a("G0 Z15 F600")
    a("G0 X10 Y220 F15000")
    a("M104 S0")
    a("SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=0")
    a("SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=0")
    a('RESPOND MSG="MACHINE-FLAT coupon done — nail test; ZERO ironing"')
    a("M84")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--bed", type=float, default=65.0)
    ap.add_argument("--nozzle", type=float, default=214.0)
    ap.add_argument("--soak", type=float, default=3.0)
    ap.add_argument("--size", type=float, default=50.0)
    ap.add_argument("--solid-layers", type=int, default=4)
    args = ap.parse_args()
    text = gen(args.bed, args.nozzle, args.soak, args.size, args.solid_layers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    pack = machine_flat_pack()
    print("wrote", args.output)
    for k, g in pack.items():
        r = evaluate_geometry(g)
        print(
            " ",
            k,
            "v=%.1f" % g.speed_mm_s,
            "Q=%.2f" % r.volumetric_mm3_s,
            "nail_ok",
            r.nail_ok,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
