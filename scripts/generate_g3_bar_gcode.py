#!/usr/bin/env python3
"""Generate adhesion + flat first-layer + anti-ooze G-code (HTPLA / Brozzl plated copper / PEX)."""

from __future__ import annotations

import argparse
from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.extrusion_motion import (
    HTPLA_BROZZL,
    RetractWipeProfile,
    gcode_apply_pa,
    gcode_travel_unretract,
    gcode_wipe_retract,
)


def e_for(dist: float, line_w: float, layer_h: float, flow: float = 1.0) -> float:
    fil_area = math.pi * (1.75 / 2.0) ** 2
    return (line_w * layer_h * dist * flow) / fil_area


def gen_bar(
    bed: float,
    nozzle: float,
    soak: float,
    profile: RetractWipeProfile = HTPLA_BROZZL,
    length: float = 100.0,
    width: float = 12.0,
    height: float = 4.0,
    layer: float = 0.2,
    line_w: float = 0.58,
    first_h: float = 0.28,
    first_flow: float = 1.14,
    first_spd_mm_s: float = 15.0,
    spacing_ratio: float = 0.84,
) -> str:
    """100mm bar — fat overlapping first-layer rows so surface is flat, not ribbed."""
    x0 = (225.0 - length) / 2.0
    y0 = (225.0 - width) / 2.0
    x1 = x0 + length
    y1 = y0 + width

    layers_z = [first_h]
    z = first_h
    while z + layer <= height + 1e-9:
        z += layer
        layers_z.append(round(z, 3))
    if layers_z[-1] < height - 1e-6:
        layers_z.append(height)

    wall_spd = 50 * 60
    first_spd = int(first_spd_mm_s * 60)
    infill_spd = 90 * 60
    travel = int(profile.travel_speed_mm_s * 60)
    spacing = line_w * spacing_ratio

    L: list = []
    a = L.append
    a("; ForgeOS G3 bar v4 — flat first layer (overlap) + wipe/retract")
    a("; TARGET_LENGTH_MM:%.3f" % length)
    a(
        "; FL_W:%.2f FL_FLOW:%.2f FL_SPD:%.0f SPACING_RATIO:%.2f"
        % (line_w, first_flow, first_spd_mm_s, spacing_ratio)
    )
    a(
        "; RETRACT:%.2fmm @%.0fmm/s WIPE:%.2fmm ZHOP:%.2f PA:%.4f"
        % (
            profile.retract_mm,
            profile.retract_speed_mm_s,
            profile.wipe_mm,
            profile.z_hop_mm,
            profile.pressure_advance,
        )
    )
    a("")
    a("FORGE_PRINT_START_ENV BED=%.2f EXTRUDER=%.2f SOAK=%.2f" % (bed, nozzle, soak))
    a("M83")
    a("G90")
    a("G92 E0")
    for line in gcode_apply_pa(profile):
        a(line)
    a("M106 S0")
    a("M221 S%d ; first-layer flow percent" % int(round(first_flow * 100)))
    a("; purge already in FORGE_PRINT_START_ENV (FORGE_PURGE) — extra short purge near part")
    a("FORGE_PURGE X=20 Y=100 LEN=40 E=5 Z=%.2f" % (first_h + 0.02))
    a("")

    # Brim — slightly wider lines, less critical flatness
    a("; brim")
    a("G0 Z%.3f F600" % first_h)
    cx = cy = None
    last_dx, last_dy = 1.0, 0.0
    for bi in range(4, 0, -1):
        inset = -bi * line_w
        xa, ya, xb, yb = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        if cx is None:
            a("G0 X%.3f Y%.3f F%d" % (xa, ya, travel))
            cx, cy = xa, ya
        else:
            for line in gcode_wipe_retract(cx, cy, first_h, last_dx, last_dy, profile, "brim hop"):
                a(line)
            for line in gcode_travel_unretract(xa, ya, first_h, profile):
                a(line)
            cx, cy = xa, ya
        for nx, ny in [(xb, ya), (xb, yb), (xa, yb), (xa, ya)]:
            dist = math.hypot(nx - cx, ny - cy)
            a(
                "G1 X%.3f Y%.3f E%.5f F%d"
                % (nx, ny, e_for(dist, line_w, first_h, first_flow), first_spd)
            )
            last_dx, last_dy = nx - cx, ny - cy
            cx, cy = nx, ny

    for line in gcode_wipe_retract(cx, cy, first_h, last_dx, last_dy, profile, "end brim"):
        a(line)

    for li, z in enumerate(layers_z):
        lh = first_h if li == 0 else (z - layers_z[li - 1])
        flow = first_flow if li == 0 else 1.0
        lw = line_w if li == 0 else 0.48
        sp = spacing if li == 0 else 0.48 * 0.92
        spd = first_spd if li == 0 else wall_spd
        isp = first_spd if li == 0 else infill_spd
        if li == 1:
            a("M221 S100")
        if li == 3:
            a("M106 S64")
        a("")
        a(";LAYER:%d Z=%.3f lw=%.2f flow=%.2f" % (li, z, lw, flow))

        sx, sy = x0, y0
        for line in gcode_travel_unretract(sx, sy, z, profile, "layer start"):
            a(line)
        cx, cy = sx, sy
        last_dx, last_dy = 1.0, 0.0

        # walls
        for peri in range(3):
            inset = peri * lw * 0.92
            xa, ya = x0 + inset, y0 + inset
            xb, yb = x1 - inset, y1 - inset
            if peri > 0:
                for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "peri"):
                    a(line)
                for line in gcode_travel_unretract(xa, ya, z, profile):
                    a(line)
                cx, cy = xa, ya
            for nx, ny in [(xb, ya), (xb, yb), (xa, yb), (xa, ya)]:
                dist = math.hypot(nx - cx, ny - cy)
                a(
                    "G1 X%.3f Y%.3f E%.5f F%d"
                    % (nx, ny, e_for(dist, lw, lh, flow), spd)
                )
                last_dx, last_dy = nx - cx, ny - cy
                cx, cy = nx, ny

        # solid fill — tight spacing on L0 for flat sheet
        inset = 3 * lw * 0.92
        xa, ya = x0 + inset, y0 + inset
        xb, yb = x1 - inset, y1 - inset
        y = ya
        direction = 1
        first_infill = True
        while y <= yb + 1e-6:
            if direction > 0:
                tx, ty, ex = xa, y, xb
            else:
                tx, ty, ex = xb, y, xa
            if first_infill:
                for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "to infill"):
                    a(line)
                for line in gcode_travel_unretract(tx, ty, z, profile):
                    a(line)
                first_infill = False
            else:
                for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "infill gap"):
                    a(line)
                for line in gcode_travel_unretract(tx, ty, z, profile):
                    a(line)
            cx, cy = tx, ty
            dist = abs(ex - tx)
            a(
                "G1 X%.3f Y%.3f E%.5f F%d"
                % (ex, ty, e_for(dist, lw, lh, flow), isp)
            )
            last_dx, last_dy = ex - tx, 0.0
            cx, cy = ex, ty
            y += sp
            direction *= -1

        for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "layer end"):
            a(line)

    a("")
    a("G0 Z%.3f F600" % (height + 12))
    a("G0 X10 Y220 F%d" % travel)
    a("M106 S0")
    a("FORGE_PRINT_END_ENV")
    a("M84")
    return "\n".join(L) + "\n"


def gen_ztune(
    bed: float,
    nozzle: float,
    soak: float,
    profile: RetractWipeProfile = HTPLA_BROZZL,
    line_w: float = 0.58,
    first_flow: float = 1.14,
    first_spd_mm_s: float = 15.0,
    spacing_ratio: float = 0.84,
) -> str:
    """Single-layer square optimized for flat fused rows on PEX."""
    size = 40.0
    x0 = (225.0 - size) / 2.0
    y0 = (225.0 - size) / 2.0
    x1, y1 = x0 + size, y0 + size
    lh = 0.28
    spd = int(first_spd_mm_s * 60)
    spacing = line_w * spacing_ratio
    L = []
    a = L.append
    a("; ForgeOS Z-TUNE v2 — flat sheet (wide lines + overlap + flow)")
    a("; FL_W:%.2f FLOW:%.2f SPD:%.0f SPACING:%.2f" % (line_w, first_flow, first_spd_mm_s, spacing))
    a("; If ribbed: still slightly high Z → BABY_DOWN 1 click; or need more flow (already high)")
    a("FORGE_PRINT_START_ENV BED=%.2f EXTRUDER=%.2f SOAK=%.2f" % (bed, nozzle, soak))
    a("M83")
    a("G90")
    a("G92 E0")
    for line in gcode_apply_pa(profile):
        a(line)
    a("M106 S0")
    a("M221 S%d" % int(round(first_flow * 100)))
    a("; start macro already purged; one more short purge left of the square")
    a("FORGE_PURGE X=15 Y=%.1f LEN=50 E=6 Z=%.2f" % (y0 - 8.0, lh + 0.02))
    a("G0 Z%.3f F600" % lh)

    cx = cy = x0
    last_dx, last_dy = 1.0, 0.0
    a("G0 X%.3f Y%.3f F9000" % (x0, y0))

    # outer shells with fat width
    for i in range(4):
        inset = i * line_w * 0.9
        xa, ya = x0 + inset, y0 + inset
        xb, yb = x1 - inset, y1 - inset
        if i > 0:
            for line in gcode_wipe_retract(cx, cy, lh, last_dx, last_dy, profile):
                a(line)
            for line in gcode_travel_unretract(xa, ya, lh, profile):
                a(line)
            cx, cy = xa, ya
        for nx, ny in [(xb, ya), (xb, yb), (xa, yb), (xa, ya)]:
            dist = math.hypot(nx - cx, ny - cy)
            a(
                "G1 X%.3f Y%.3f E%.5f F%d"
                % (nx, ny, e_for(dist, line_w, lh, first_flow), spd)
            )
            last_dx, last_dy = nx - cx, ny - cy
            cx, cy = nx, ny

    # solid fill with overlap
    y = y0 + 4 * line_w * 0.9
    y_end = y1 - 4 * line_w * 0.9
    direction = 1
    first = True
    while y <= y_end + 1e-6:
        xa = x0 + 4 * line_w * 0.9
        xb = x1 - 4 * line_w * 0.9
        if direction > 0:
            tx, ty, ex = xa, y, xb
        else:
            tx, ty, ex = xb, y, xa
        if first:
            for line in gcode_wipe_retract(cx, cy, lh, last_dx, last_dy, profile):
                a(line)
            for line in gcode_travel_unretract(tx, ty, lh, profile):
                a(line)
            first = False
        else:
            for line in gcode_wipe_retract(cx, cy, lh, last_dx, last_dy, profile):
                a(line)
            for line in gcode_travel_unretract(tx, ty, lh, profile):
                a(line)
        a(
            "G1 X%.3f Y%.3f E%.5f F%d"
            % (ex, ty, e_for(abs(ex - tx), line_w, lh, first_flow), spd)
        )
        last_dx, last_dy = ex - tx, 0.0
        cx, cy = ex, ty
        y += spacing
        direction *= -1

    for line in gcode_wipe_retract(cx, cy, lh, last_dx, last_dy, profile, "ztune end"):
        a(line)
    a("G0 Z10 F600")
    a("G0 X10 Y220 F9000")
    a("M104 S0")
    a("SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=0")
    a("SET_HEATER_TEMPERATURE HEATER=heater_bed_outer TARGET=0")
    a('RESPOND MSG="Z-TUNE v2 done — want flat fused sheet, not ribs"')
    a("M84")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--mode", choices=["bar", "ztune"], default="bar")
    ap.add_argument("--bed", type=float, default=None)
    ap.add_argument("--nozzle", type=float, default=None)
    ap.add_argument("--soak", type=float, default=None)
    ap.add_argument("--use-stack", action="store_true")
    ap.add_argument("--ambient", type=float, default=14.0)
    args = ap.parse_args()

    bed, nozzle, soak = 65.0, 214.0, 5.0
    profile = HTPLA_BROZZL
    fl_w, fl_flow, fl_spd, sp_ratio = 0.58, 1.14, 15.0, 0.84

    if args.use_stack:
        from forgeos.stack_profile import compose_stack

        stack = compose_stack(ambient_temp_c=args.ambient, z_adjust_seed=0.08)
        bed, nozzle, soak = stack.bed_c, stack.nozzle_c, stack.soak_min
        # prefer material first_layer if present via pack raw — stack already has fields
        fl_w = max(0.55, stack.line_width_mm)
        fl_flow = max(1.12, stack.first_layer_flow)
        fl_spd = min(16.0, stack.first_layer_speed_mm_s)
        profile = RetractWipeProfile(
            retract_mm=stack.retract_mm,
            unretract_mm=stack.retract_mm,
            retract_speed_mm_s=stack.retract_speed_mm_s,
            unretract_speed_mm_s=stack.unretract_speed_mm_s,
            wipe_mm=stack.wipe_mm,
            wipe_speed_mm_s=stack.wipe_speed_mm_s,
            z_hop_mm=stack.z_hop_mm,
            travel_speed_mm_s=stack.travel_speed_mm_s,
            pressure_advance=stack.pressure_advance,
            pressure_advance_smooth_time=stack.pressure_advance_smooth_time,
        )
        print(
            "stack flat-FL w=%.2f flow=%.2f spd=%.1f noz=%.0f retract=%.2f"
            % (fl_w, fl_flow, fl_spd, nozzle, profile.retract_mm)
        )

    if args.bed is not None:
        bed = args.bed
    if args.nozzle is not None:
        nozzle = args.nozzle
    if args.soak is not None:
        soak = args.soak

    if args.mode == "ztune":
        text = gen_ztune(bed, nozzle, soak, profile, fl_w, fl_flow, fl_spd, sp_ratio)
    else:
        text = gen_bar(
            bed, nozzle, soak, profile,
            line_w=fl_w, first_flow=fl_flow, first_spd_mm_s=fl_spd, spacing_ratio=sp_ratio,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print("wrote", args.output, "mode", args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
