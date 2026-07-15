# Calibration protocol — Neptune 4 Pro / OpenNeptune / ForgeOS

God-tier print quality is an **ordered engineering process**, not vibes.
Skipping or reordering steps invalidates later results.

## Safety

```text
Host: SafetyGate.arm("campaign") token required for --execute
Printer: FORGE_ARM PURPOSE=campaign  (mirrored by runner)
Never: optimizers writing outside envelopes
```

## Two suites

| Suite | When | Command |
|---|---|---|
| **onetime** | New machine, new nozzle, OpenNeptune flash, bed screws changed | `python3 -m forgeos.calibration dry-run --suite onetime` |
| **finetune** | Spool change, chase G4/G5, corner/surface perfection | `--suite finetune` |
| **full** | Both, in order | `--suite full` (default) |

```bash
# Plan only (JSON)
python3 -m forgeos.calibration plan --suite onetime

# Dry-run: write all cal gcodes + report (no printer motion)
python3 scripts/run_full_cal.py --suite full

# Patterns only
python3 -m forgeos.calibration patterns --out artifacts/calibration

# Live AUTO steps (PID/mesh/…) — interactive steps still pause
python3 scripts/run_full_cal.py --suite onetime --execute --arm --host 192.168.1.178
```

## One-time sequence (non-negotiable order)

Aligned with **OpenNept4une** wiki + **Klipper** docs + N4 Pro dual-bed:

1. **Preflight** — `FORGE_PREFLIGHT` (material vs Brozzl soft nozzle policy)
2. **Bed screws** — `FORGE_BED_SCREWS_TUNE` / `SCREWS_TILT_CALCULATE`  
   Do **not** over-compress springs (center-high mesh). Any screw change → redo probe Z.
3. **Probe Z** — `FORGE_PROBE_CAL` cold paper → Accept → `SAVE_CONFIG`  
   (OpenNeptune `CALIBRATE_PROBE_Z_OFFSET`)
4. **Rotation distance** — `FORGE_EXTRUDE_CAL` / mark 120 mm, command 100 mm  
   `new_rd = old_rd × actual/commanded`  
   `python3 -m forgeos.calibration compute-rd --current 7.5 --actual 98.5`
5. **PID all** — `FORGE_PID_ALL` nozzle + **inner bed** + **outer bed** (N4 Pro only) → `SAVE_CONFIG`
6. **Input shaper** — `FORGE_SHAPER_CAL` if ADXL/Beacon; else soft-skip (pass `--adxl` when present)
7. **Dual-bed soak + precision mesh** — heat both zones, soak, `FORGE_MESH_PRECISION`  
   Target p2p ≤ **0.25 mm** good / **0.80 mm** G2 hard fail
8. **First layer** — `first_layer_patch.gcode` on clean Wham Bam PEX; baby-step; `Z_OFFSET_APPLY_PROBE`
9. **Flow** — single-wall shell → measure → `FORGE_COMPUTE_FLOW` / `compute-flow`  
   **After** RD, **before** PA
10. **Pressure advance** — DD `TUNING_TOWER … FACTOR=0.005` → height × 0.005  
    Set in **filament start gcode** (OpenNeptune practice; `printer.cfg` is fallback only)
11. **Retract / wipe / z-hop** — `FORGE_RETRACT_CAL` seed 1.20 / 40 / 1.4 / 0.25
12. **Coupon** — G3 100 mm bar (`generate_g3_bar_gcode.py --use-stack`)
13. **Measure** — caliper CSV → `scripts/import_caliper_csv.py` → G3 \|err\| ≤ 0.20 mm (aim 0.15)
14. **Promote** — `FORGE_APPLY_CAL_RESULT` + `configs/saved_state_shop_n4pro.yaml`

## Fine-tune (god-tier loop)

1. Nozzle temp ±5 °C (HTPLA + plated copper: often slight cool bias)
2. PA fine band ±0.005 around seed (`pa_fine.gcode`)
3. Flow fine ±2%
4. Machine-flat first layer (s=w, flow≈1.0, **zero ironing**)
5. **G4** — 3× bars, span ≤ 0.10 mm
6. **G5** — ≥25% faster than T0 **while G3/G4 hold**
7. Optional anneal → **G6**

## Compute helpers

```bash
python3 -m forgeos.calibration compute-flow --measured 0.46 --line-width 0.44
python3 -m forgeos.calibration compute-pa --height 6.2
python3 -m forgeos.calibration compute-rd --current 7.5 --actual 98.5
```

## Gates

```bash
python3 scripts/run_gates.py --g0
python3 scripts/run_gates.py --g3-error 0.12 --g4-span 0.06 --g5-duration 900 --g5-baseline 1400
python3 scripts/run_gates.py --live-g1-g2 --host 192.168.1.178 --shaper-ok
```

| Gate | Bar |
|---|---|
| G3 | \|err\| ≤ 0.20 mm / 100 mm |
| G4 | 3× span ≤ 0.10 mm |
| G5 | ≥25% faster vs baseline with G3/G4 green |
| G6 | Post-anneal dims in band |
| G7 | ≥2 h soak, 0 MCU losses |

## N4 Pro notes (research)

- Dual-zone bed: always PID and heat **`heater_bed`** + **`heater_bed_outer`**
- Outer zone auto-logic in OpenNeptune activates beyond center ~62.5–172.5 mm or high bed temps
- Geared direct-drive → PA typically **0.02–0.06**, TUNING_TOWER factor **0.005**
- Shop stack seed: Z=−0.480, bed 65 °C, nozzle 214 °C, PA 0.030, PEX + Brozzl 0.4 + HTPLA

## Macros

`FORGE_CAL_FULL`, `FORGE_BED_SCREWS_TUNE`, `FORGE_PID_ALL`, `FORGE_SHAPER_CAL`,
`FORGE_PROBE_CAL`, `FORGE_EXTRUDE_CAL`, `FORGE_FLOW_CAL`, `FORGE_COMPUTE_FLOW`,
`FORGE_PA_CAL`, `FORGE_COMPUTE_PA`, `FORGE_PA_FINE`, `FORGE_FIRST_LAYER_CAL`,
`FORGE_RETRACT_CAL`, `FORGE_PRINT_COUPON`, `FORGE_APPLY_CAL_RESULT`, `FORGE_ARM`
