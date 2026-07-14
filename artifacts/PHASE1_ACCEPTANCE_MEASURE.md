# Phase 1 Acceptance — Measure Card (G3 + T0)

**File:** `forgeos_g3_htpla_100mm_bar_v2.gcode`  
**Bar CAD length (X):** **100.00 mm**  
**Stack:** Wham Bam PEX · Brozzl plated copper 0.4 · Protopasta HTPLA  
**Z adjust (locked):** **−0.480 mm**

## Timeline (this run)

| Phase | Observed |
|---|---|
| Start + dual-bed heat + 5 min soak + mesh | ~19 min wall |
| Active print (`print_duration`) | **1298 s ≈ 21.6 min** → **T0** |
| Wall clock total (`total_duration`) | **2362 s ≈ 39.4 min** |
| Filament used | ~2331 mm |

## Measured dims (operator)

| Metric | Nominal | Measured | Error (meas − nom) |
|---|---|---|---|
| Length **X** (long axis) | 100.00 mm | **99–100 mm** | **−1.0 … 0.0 mm** |
| Width **Y** | 10.00 mm | (not reported) | — |
| Height **Z** | 5.00 mm | (not reported) | — |

- [x] First layer continuous? (reprint at Z=−0.480; operator continued)
- [ ] Elephant foot estimate: ______ mm  
- [ ] Delam / holes / under-extrusion notes: ________________  
- [x] Actual print duration: **21.6 min** (print_duration) → **T0**  
- [ ] Ambient T/RH during print: basement shop baseline ~14 °C / ~65 %RH (soft)

## Pass (G3)

Gate: |error| on 100 mm **≤ 0.20 mm** (aim ≤ 0.15 mm)

| Result | Status |
|---|---|
| If X ≈ **100.0** | **PASS** |
| If X ≈ **99.0** | **FAIL** (−1.0 mm) |
| Reported **99–100 mm** band | **PROVISIONAL / borderline** — not a single hard pass |

**G3 verdict (this log):** **PROVISIONAL** — upper bound meets nominal; lower bound fails gate by ~0.8 mm.  
**Action:** remeasure long-axis with caliper at 3 points (ends + mid), report one mean value to 0.01–0.05 mm if possible.

## T0 cycle time

| Metric | Value |
|---|---|
| T0 print_duration | **21.6 min** (1298 s) |
| Wall clock (incl. soak/mesh) | **39.4 min** (2362 s) |

## Process lock used

```
FORGE_SET_Z_ADJUST Z=-0.480
bed 65 / nozzle 214 / soak 5 / PA 0.0315
first layer: 0.28 h · 0.58 w · flow 114% · ~14 mm/s
```
