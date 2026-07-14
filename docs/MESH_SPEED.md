# Bed mesh: mechanics & max speed without losing accuracy

## Why it was ~20 minutes

| Factor | Your old config | Cost |
|--------|-----------------|------|
| Grid | **11 × 11 = 121** points | Dominant |
| Samples | **3** per point (median) | ×3 probes |
| Probe speed | **6 mm/s** | Slow Z approach |
| Retract | **3 mm** @ ~6 mm/s | Per sample |
| Retries | tol 0.025, 3 retries | Extra probes if noisy |
| XY hop | horizontal_move_z **5** | Extra Z travel |

Rough time: \(121 × 3 × ~2.5\,\mathrm{s} ≈ 15\text{–}25\,\mathrm{min}\).

That is a **mapping lab** mesh, not an every-print mesh.

## Physics: what accuracy actually needs

1. **Compensation field smoothness** — PEI/PEX on a N4 Pro is mostly low-order (tilt + gentle bowl). Bicubic interpolation reconstructs that from **5×5 or 7×7**.
2. **Probe noise** — median of 2 samples beats 1; 3 is diminishing returns if probe is clean and tol is sane.
3. **Thermal state** — mesh at **print bed temp** after soak; a cold mesh is “precise” and still **wrong** when hot.
4. **Repeatability** — better to have a **saved hot profile** you **load** than a slow cold re-mesh.

## Max-speed policy (ForgeOS)

| Mode | Macro | Grid | When | Typical time* |
|------|--------|------|------|----------------|
| **Load** | `FORGE_MESH_LOAD` / `MESH=0` | — | **Every normal print** | **&lt; 1 s** |
| **Fast** | `FORGE_MESH_FAST` / `MESH=1` | 5×5 | Coupon / after small bump | **~0.5–1.5 min** |
| **Balanced** | `FORGE_MESH_BALANCED` / `MESH=2` | 7×7 | Session start | **~1.5–4 min** |
| **Precision** | `FORGE_MESH_PRECISION` / `MESH=3` | 9×9 | G2 / new sheet / weekly | **~4–10 min** |

\*After probe speed upgrade (10 mm/s, samples=2). Absolute times still depend on MCU/probe.

Print start default is **`MESH=0` (load profile)**.

```gcode
FORGE_PRINT_START_ENV BED=65 EXTRUDER=214 SOAK=1 MESH=0
; force a fast remap:
FORGE_PRINT_START_ENV BED=65 EXTRUDER=214 SOAK=2 MESH=1
```

## Probe knobs (printer.cfg)

Recommended production defaults (still accurate):

```ini
[probe]
speed: 10.0              # was 6.0 — inductive/CR-class ok at 8–12
# lift_speed: 15.0       # if your Klipper build supports it
samples: 2               # was 3
sample_retract_dist: 2.0 # was 3.0
samples_tolerance: 0.035 # was 0.025 — fewer false retries
samples_tolerance_retries: 2

[bed_mesh]
speed: 200               # XY between points (was 150)
horizontal_move_z: 3     # was 5
probe_count: 7, 7        # default grid if you forget PROBE_COUNT=
algorithm: bicubic
mesh_pps: 3, 3
```

**Do not** push probe speed so high that probes bounce (watch `PROBE_ACCURACY`). If stdev rises, back off to 8 mm/s.

## What not to do

- Full **11×11×3** before every coupon  
- Mesh **cold** then print **hot**  
- Ironing to hide a bad mesh  
- Disable mesh entirely without a known-good loaded profile  

## Adaptive mesh (future)

Klipper `BED_MESH_CALIBRATE ADAPTIVE=1` needs object polygons (exclude object / slicer). KAMP Adaptive_Meshing was not installed under `config/KAMP/`. Optional later for large plates with small parts — only probes under the print.

## Validation (keep precision honest)

After changing mesh speed:

1. `PROBE_ACCURACY` at bed center — stdev ideally &lt; 0.01–0.015 mm  
2. `FORGE_MESH_BALANCED` hot → `BED_MESH_PROFILE SAVE=default` → `SAVE_CONFIG`  
3. Print first-layer square; compare to previous  
4. G3 bar still within 0.20 mm  

If first layer corners lift only after going 5×5, bump session mesh to **7×7** (`MESH=2`), not back to 11×11.
