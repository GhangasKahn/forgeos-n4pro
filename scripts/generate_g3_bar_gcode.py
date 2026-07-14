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
    line_w: float = 0.44,
    first_h: float = 0.28,
    first_flow: float = 1.00,
    first_spd_mm_s: float = 12.0,
    spacing_ratio: float = 1.00,
    upper_line_w: float = 0.44,
    upper_spacing_ratio: float = 1.00,
    upper_speed_mm_s: float = 120.0,
    top_speed_mm_s: float = 80.0,
    monotonic: bool = True,
) -> str:
    """100mm bar — machine-flat: s=w, flow balanced, MONOTONIC solids, ZERO ironing."""
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

    wall_spd = int(min(80.0, upper_speed_mm_s) * 60)
    first_spd = int(first_spd_mm_s * 60)
    infill_spd = int(upper_speed_mm_s * 60)
    top_spd = int(top_speed_mm_s * 60)
    travel = int(profile.travel_speed_mm_s * 60)
    spacing = line_w * spacing_ratio

    L: list = []
    a = L.append
    a("; ForgeOS G3 bar v7 — MACHINE-FLAT ZERO IRONING (monotonic, s=w, Q-limited)")
    a("; TARGET_LENGTH_MM:%.3f  (CAD length; use --length to compensate shrink/short)" % length)
    a(
        "; FL_W:%.2f FL_FLOW:%.2f FL_SPD:%.0f SPACING_RATIO:%.3f STEP:%.3fmm MONO=%s"
        % (line_w, first_flow, first_spd_mm_s, spacing_ratio, spacing, monotonic)
    )
    a("; FLAT_RULE: e_area = spacing*h; flow*line_w = spacing; no ironing; see docs/MACHINE_FLAT_ZERO_IRON.md")
    a("; UPPER_SPD:%.0f TOP_SPD:%.0f" % (upper_speed_mm_s, top_speed_mm_s))
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
    a("FORGE_FLAT_SET LINE_W=%.3f FLOW=%.3f PA=%.4f Q_MAX=12.0" % (line_w, first_flow, profile.pressure_advance))
    a("FORGE_FLAT_SURFACE_MODE ROLE=first")
    a("M106 S0")
    a("M221 S%d ; first-layer flow percent" % int(round(first_flow * 100)))
    a("; purge already in FORGE_PRINT_START_ENV (FORGE_PURGE) — extra short purge near part")
    a("FORGE_PURGE X=20 Y=100 LEN=40 E=5 Z=%.2f" % (first_h + 0.02))
    a("")

    # Brim — same side-by-side pitch as part (not piled)
    a("; brim (side-by-side pitch)")
    a("G0 Z%.3f F600" % first_h)
    cx = cy = None
    last_dx, last_dy = 1.0, 0.0
    for bi in range(4, 0, -1):
        inset = -bi * spacing
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

    n_layers = len(layers_z)
    for li, z in enumerate(layers_z):
        lh = first_h if li == 0 else (z - layers_z[li - 1])
        flow = first_flow if li == 0 else 1.0
        lw = line_w if li == 0 else upper_line_w
        sp = spacing if li == 0 else (upper_line_w * upper_spacing_ratio)
        is_top = li == n_layers - 1 and li > 0
        if li == 0:
            spd = first_spd
            isp = first_spd
            a("FORGE_FLAT_SURFACE_MODE ROLE=first")
        elif is_top:
            spd = min(wall_spd, top_spd)
            isp = top_spd
            a("FORGE_FLAT_SURFACE_MODE ROLE=top")
        else:
            spd = wall_spd
            isp = infill_spd
            a("FORGE_FLAT_SURFACE_MODE ROLE=solid")
        if li == 1:
            a("M221 S100")
        a("")
        a(
            ";LAYER:%d Z=%.3f lw=%.2f flow=%.2f step=%.3f mono=%s isp=%d"
            % (li, z, lw, flow, sp, monotonic, isp)
        )

        sx, sy = x0, y0
        for line in gcode_travel_unretract(sx, sy, z, profile, "layer start"):
            a(line)
        cx, cy = sx, sy
        last_dx, last_dy = 1.0, 0.0

        # walls — pitch = spacing (volume-matched shells)
        for peri in range(3):
            inset = peri * sp
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

        # solid fill — MONOTONIC (+X only) kills reverse-direction V-grooves
        inset = 3 * sp
        xa, ya = x0 + inset, y0 + inset
        xb, yb = x1 - inset, y1 - inset
        y = ya
        while y <= yb + 1e-6:
            if monotonic:
                tx, ty, ex = xa, y, xb
            else:
                # legacy zigzag (not recommended for nail-flat)
                # direction derived from row index
                if int(round((y - ya) / sp)) % 2 == 0:
                    tx, ty, ex = xa, y, xb
                else:
                    tx, ty, ex = xb, y, xa
            for line in gcode_wipe_retract(cx, cy, z, last_dx, last_dy, profile, "infill"):
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
    line_w: float = 0.44,
    first_flow: float = 1.00,
    first_spd_mm_s: float = 12.0,
    spacing_ratio: float = 1.00,
) -> str:
    """Single-layer square — god-tier flat: side-by-side lines on PEX."""
    size = 40.0
    x0 = (225.0 - size) / 2.0
    y0 = (225.0 - size) / 2.0
    x1, y1 = x0 + size, y0 + size
    lh = 0.28
    spd = int(first_spd_mm_s * 60)
    spacing = line_w * spacing_ratio
    L = []
    a = L.append
    a("; ForgeOS Z-TUNE v3 — GOD-TIER FLAT (side-by-side, spacing_ratio=1.0)")
    a("; FL_W:%.2f FLOW:%.2f SPD:%.0f STEP:%.3f" % (line_w, first_flow, first_spd_mm_s, spacing))
    a("; Want glass-flat sheet: lines kiss, not pile. Gaps → ratio 0.97 or flow 1.02; piles → ratio 1.0 / lower flow")
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

    # outer shells — side-by-side pitch
    for i in range(4):
        inset = i * spacing
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

    # solid fill — side-by-side (step = line_w * spacing_ratio)
    y = y0 + 4 * spacing
    y_end = y1 - 4 * spacing
    direction = 1
    first = True
    while y <= y_end + 1e-6:
        xa = x0 + 4 * spacing
        xb = x1 - 4 * spacing
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
    a('RESPOND MSG="Z-TUNE v3 FLAT done — side-by-side sheet, not piled ribs"')
    a("M84")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--mode", choices=["bar", "ztune"], default="bar")
    ap.add_argument("--bed", type=float, default=None)
    ap.add_argument("--nozzle", type=float, default=None)
    ap.add_argument("--soak", type=float, default=None)
    ap.add_argument(
        "--length",
        type=float,
        default=100.0,
        help="CAD bar length mm (e.g. 100.5 if last print measured ~99.5)",
    )
    ap.add_argument("--line-w", type=float, default=0.44, help="first-layer line width mm")
    ap.add_argument(
        "--spacing-ratio",
        type=float,
        default=1.0,
        help="row step / line_w; 1.0=side-by-side flat, <1 piles, >1 gaps",
    )
    ap.add_argument("--first-flow", type=float, default=1.0, help="first-layer flow multiplier")
    ap.add_argument("--first-speed", type=float, default=30.0, help="first-layer speed mm/s")
    ap.add_argument(
        "--machine-flat",
        action="store_true",
        help="use forgeos.flat_surface machine_flat_pack (Q-limited high-speed solids, mono)",
    )
    ap.add_argument("--use-stack", action="store_true")
    ap.add_argument("--ambient", type=float, default=14.0)
    args = ap.parse_args()

    bed, nozzle, soak = 65.0, 214.0, 5.0
    profile = HTPLA_BROZZL
    # Machine-flat defaults: s=w, f=1, no pile-up (see docs/MACHINE_FLAT_ZERO_IRON.md)
    fl_w = float(args.line_w)
    fl_flow = float(args.first_flow)
    fl_spd = float(args.first_speed)
    sp_ratio = float(args.spacing_ratio)
    length = float(args.length)
    upper_spd, top_spd = 120.0, 80.0
    if args.machine_flat:
        from forgeos.flat_surface import machine_flat_pack, pack_reports

        pack = machine_flat_pack(pa=profile.pressure_advance)
        fl_w = pack["first_layer"].line_width_mm
        fl_flow = pack["first_layer"].flow
        fl_spd = pack["first_layer"].speed_mm_s
        sp_ratio = pack["first_layer"].spacing_ratio
        upper_spd = pack["solid"].speed_mm_s
        top_spd = pack["top_solid"].speed_mm_s
        for name, rep in pack_reports(pack).items():
            print(
                "machine_flat",
                name,
                "v=%.1f" % pack[name].speed_mm_s,
                "Q=%.2f" % rep.volumetric_mm3_s,
                "nail_ok",
                rep.nail_ok,
            )

    if args.use_stack:
        from forgeos.stack_profile import compose_stack

        stack = compose_stack(ambient_temp_c=args.ambient, z_adjust_seed=-0.480)
        bed, nozzle, soak = stack.bed_c, stack.nozzle_c, stack.soak_min
        # Keep explicit flat geometry unless user overrode CLI defaults only for temps/PA
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
            "stack temps/PA only; FLAT geometry w=%.2f flow=%.2f spd=%.1f ratio=%.2f"
            % (fl_w, fl_flow, fl_spd, sp_ratio)
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
            length=length,
            line_w=fl_w, first_flow=fl_flow, first_spd_mm_s=fl_spd, spacing_ratio=sp_ratio,
            upper_speed_mm_s=upper_spd, top_speed_mm_s=top_spd, monotonic=True,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(
        "wrote",
        args.output,
        "mode",
        args.mode,
        "length",
        length if args.mode == "bar" else "n/a",
        "step_mm",
        round(fl_w * sp_ratio, 3),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
