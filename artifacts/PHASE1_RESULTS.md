# Phase 1 Live Test Results

**Date:** 2026-07-14  
**Printer:** `znp-k1` @ `192.168.1.178`  
**Repo:** `/Users/kylefetes/forgeos-n4pro` + `/home/mks/forgeos-n4pro`

## What ran

| Step | Result |
|---|---|
| Local unit tests (30) | PASS (prior) |
| G0 static gate | **PASS** |
| Deploy ForgeOS to printer | **PASS** |
| Config backup | `/home/mks/printer_data/backup/forgeos_phase1_*` |
| Include `forgeos/forge_phase1.cfg` | **PASS** (fixed nested include paths) |
| Klipper ready + FORGE macros loaded | **PASS** (~39 FORGE macros) |
| G1 hardware (MCU ready) | **PASS** |
| Dual-bed heat to 60 °C + 1–2 min soak | **PASS** (inner & outer ~60 °C) |
| Macro smoke (`FORGE_SET_AMBIENT`, `PREFLIGHT`, env, moisture) | **PASS** |
| G28 + `BED_MESH_CALIBRATE` | **PASS** (completed; see mesh report) |

## T0 environment baseline (software)

From `environments/basement_default.yaml` (14 °C / 65 % RH / open):

| Param | Value |
|---|---|
| bin | `cold_humid` |
| bed | ~62.6 °C |
| nozzle | ~216.7 °C |
| soak | ~6.6 min |
| during speed factor | ~0.80 |

## Gates

| Gate | Status | Notes |
|---|---|---|
| G0 | PASS | materials + unit tests |
| G1 | PASS | printer ready |
| G2 | deferred / soft | ADXL/shaper not installed yet; mesh exercised |
| G3–G5 | **not yet** | require HTPLA 100 mm coupon print + calipers |

## Acceptance remaining (Phase 1 complete when)

1. Print HTPLA 100 mm calibration bar with env-aware start  
2. Measure → journal dims (G3 aim ±0.20 mm)  
3. Record wall-clock cycle time as **T0**  
4. (Optional) 3× reprints for G4 precision span  

## Operator commands used

```gcode
FORGE_SET_AMBIENT TEMP=14 RH=65 DRAFT=0.3
FORGE_SET_ENCLOSURE MODE=open
FORGE_SET_NOZZLE TYPE=hardened DIA=0.4
FORGE_SET_MATERIAL SKU=protopasta_htpla
FORGE_PREFLIGHT
FORGE_APPLY_ENV_TARGETS BED=62.6 NOZ=216.7 SOAK=6.6
FORGE_PRINT_START_ENV
```

## Artifacts

- `artifacts/phase1_report.json` — heat path  
- `artifacts/phase1_mesh_report.json` — mesh path  
- `artifacts/phase1_journal.sqlite3` — event journal  

## Fixes applied during Phase 1

1. Nested Klipper include paths (`forgeos/forgeos/...` → relative)  
2. Moonraker object query URL-encoding for `heater_generic heater_bed_outer`  
3. Heat wait via temperature poll instead of long blocking `TEMPERATURE_WAIT` HTTP  
4. `START_PRINT` only defined in env overlay (no duplicate)  
