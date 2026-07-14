#!/usr/bin/env python3
"""First-layer comparison coupon (PA-test style): side-by-side panels.

Each panel is a solid single-layer rectangle with different geometry so you can
pick the flattest look by eye — same idea as a pressure-advance pattern, but
for first-layer line width / step / flow.

Default matrix (left → right, bottom → top):
  Columns: spacing_ratio  0.92 | 0.96 | 1.00 | 1.04
  Rows:    first_flow     0.96 | 1.00 | 1.04

Fixed: line_w=0.44, first_h=0.28, speed 12 mm/s, PA from HTPLA_BROZZL.
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
    gcode_apply_pa,
    gcode_travel_unretract,
    gcode_wipe_retract,
)


def e_for(dist: float, line_w: float, layer_h: float, flow: float) -> float:
    fil_area = math.pi * (1.75 / 2.0) ** 2
    return (line_w * layer_h * dist * flow) / fil_area


def fill_panel(
    a,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z: float,
    line_w: float,
    step: float,
    flow: float,
    spd: int,
    travel: int,
    profile,
    cxcy,
):
    """Solid rect fill, long strokes along +X. Returns (cx, cy, last_dx, last_dy)."""
    cx, cy, last_dx, last_dy = cxcy
    # start bottom-left
    y = y0 + line_w * 0.5
    y_end = y1 - line_w * 0.5
    direction = 1
    first = True
    while y <= y_end + 1e-9:
        if direction > 0:
            tx, ex = x0 + line_w * 0.5, x1 - line_w * 0.5
        else:
            tx, ex = x1 - line_w * 0.5, x0 + line_w * 0.5
        ty = y
        if first:
            for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "panel"):
                a(line)
            for line in gcode_travel_unretract(tx, ty, z, profile):
                a(line)
            first = False
        else:
            for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile):
                a(line)
            for line in gcode_travel_unretract(tx, ty, z, profile):
                a(line)
        dist = abs(ex - tx)
        a(
            "G1 X%.3f Y%.3f E%.5f F%d"
            % (ex, ty, e_for(dist, line_w, z, flow), spd)
        )
        last_dx, last_dy = ex - tx, 0.0
        cx, cy = ex, ty
        y += step
        direction *= -1
    return cx, cy, last_dx, last_dy


def gen(
    bed: float = 65.0,
    nozzle: float = 214.0,
    soak: float = 3.0,
    line_w: float = 0.44,
    first_h: float = 0.28,
    speed_mm_s: float = 12.0,
    spacing_ratios=None,
    flows=None,
    panel_w: float = 28.0,
    panel_h: float = 22.0,
    gap: float = 6.0,
) -> str:
    if spacing_ratios is None:
        spacing_ratios = [0.92, 0.96, 1.00, 1.04]
    if flows is None:
        flows = [0.96, 1.00, 1.04]

    profile = HTPLA_BROZZL
    spd = int(speed_mm_s * 60)
    travel = int(profile.travel_speed_mm_s * 60)

    ncols = len(spacing_ratios)
    nrows = len(flows)
    total_w = ncols * panel_w + (ncols - 1) * gap
    total_h = nrows * panel_h + (nrows - 1) * gap
    # center on 225 bed
    ox = (225.0 - total_w) / 2.0
    oy = (225.0 - total_h) / 2.0

    L: list = []
    a = L.append
    a("; ForgeOS FIRST-LAYER COMPARE (PA-style multi-panel)")
    a("; line_w=%.2f first_h=%.2f speed=%.0fmm/s" % (line_w, first_h, speed_mm_s))
    a("; COLS spacing_ratio (L→R): %s" % " | ".join("%.2f" % r for r in spacing_ratios))
    a("; ROWS first_flow (B→T): %s" % " | ".join("%.2f" % f for f in flows))
    a("; Pick flattest panel: side-by-side beads, no pile ridges, no gaps")
    a("; Legend strips: short single-line row under each col = spacing only @ flow 1.00")
    a("")
    a("FORGE_PRINT_START_ENV BED=%.2f EXTRUDER=%.2f SOAK=%.2f" % (bed, nozzle, soak))
    a("M83")
    a("G90")
    a("G92 E0")
    for line in gcode_apply_pa(profile):
        a(line)
    a("M106 S0")
    a("M221 S100")
    a("FORGE_PURGE X=15 Y=12 LEN=100 E=12 Z=%.2f" % (first_h + 0.02))
    a("G0 Z%.3f F600" % first_h)
    a("")

    cx, cy = ox, oy
    last_dx, last_dy = 1.0, 0.0

    # Legend: one thin stripe per column under the grid (spacing demo @ flow 1.0)
    legend_y0 = oy - gap - 8.0
    legend_y1 = oy - gap - 2.0
    a("; === legend stripes (spacing only, flow=1.00) ===")
    for ci, ratio in enumerate(spacing_ratios):
        step = line_w * ratio
        x0 = ox + ci * (panel_w + gap)
        x1 = x0 + panel_w
        a("; LEGEND col=%d spacing_ratio=%.2f step=%.3f" % (ci, ratio, step))
        a("M117 FL sp=%.2f" % ratio)
        cx, cy, last_dx, last_dy = fill_panel(
            a,
            x0,
            legend_y0,
            x1,
            legend_y1,
            first_h,
            line_w,
            step,
            1.0,
            spd,
            travel,
            profile,
            (cx, cy, last_dx, last_dy),
        )

    # Main matrix
    a("")
    a("; === main matrix ===")
    for ri, flow in enumerate(flows):
        for ci, ratio in enumerate(spacing_ratios):
            step = line_w * ratio
            x0 = ox + ci * (panel_w + gap)
            y0 = oy + ri * (panel_h + gap)
            x1 = x0 + panel_w
            y1 = y0 + panel_h
            a(
                "; PANEL r=%d c=%d spacing_ratio=%.2f flow=%.2f step=%.3fmm"
                % (ri, ci, ratio, flow, step)
            )
            a("M117 r%.2f f%.2f" % (ratio, flow))
            # perimeter box so panel edge is obvious
            for line in gcode_wipe_retract(cx, cy, first_h, last_dx, last_dy, profile, "to box"):
                a(line)
            for line in gcode_travel_unretract(x0, y0, first_h, profile):
                a(line)
            cx, cy = x0, y0
            for nx, ny in [(x1, y0), (x1, y1), (x0, y1), (x0, y0)]:
                dist = math.hypot(nx - cx, ny - cy)
                a(
                    "G1 X%.3f Y%.3f E%.5f F%d"
                    % (nx, ny, e_for(dist, line_w, first_h, flow), spd)
                )
                last_dx, last_dy = nx - cx, ny - cy
                cx, cy = nx, ny
            cx, cy, last_dx, last_dy = fill_panel(
                a,
                x0 + line_w,
                y0 + line_w,
                x1 - line_w,
                y1 - line_w,
                first_h,
                line_w,
                step,
                flow,
                spd,
                travel,
                profile,
                (cx, cy, last_dx, last_dy),
            )

    for line in gcode_wipe_retract(cx, cy, first_h, last_dx, last_dy, profile, "end"):
        a(line)
    a("G0 Z15 F600")
    a("G0 X10 Y220 F%d" % travel)
    a("M104 S0")
    a("SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=0")
    a("SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=0")
    a(
        'RESPOND MSG="FL COMPARE done — cols spacing 0.92/0.96/1.00/1.04 L→R; rows flow 0.96/1.00/1.04 B→T"'
    )
    a("M84")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="First-layer multi-panel compare (PA-style)")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--bed", type=float, default=65.0)
    ap.add_argument("--nozzle", type=float, default=214.0)
    ap.add_argument("--soak", type=float, default=3.0)
    ap.add_argument("--line-w", type=float, default=0.44)
    ap.add_argument("--first-h", type=float, default=0.28)
    ap.add_argument("--speed", type=float, default=12.0)
    args = ap.parse_args()
    text = gen(
        bed=args.bed,
        nozzle=args.nozzle,
        soak=args.soak,
        line_w=args.line_w,
        first_h=args.first_h,
        speed_mm_s=args.speed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print("wrote", args.output, "bytes", len(text))
    print("matrix: spacing cols 0.92/0.96/1.00/1.04  ×  flow rows 0.96/1.00/1.04")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
