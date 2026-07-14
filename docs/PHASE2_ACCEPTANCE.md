# Phase 2 — Precision process lock (zero-vision)

**Goal:** Stable, fast, accurate shop loop without cameras.  
**Stack:** PEX + Brozzl plated copper 0.4 + HTPLA · Z=−0.480 · dual-bed adaptive · machine-flat · fast mesh.

## Phase 2 gates

| Gate | Action | Pass |
|------|--------|------|
| P2-M | Hot dual-bed **7×7** mesh @ 65 °C → `default` profile | Mesh complete, profile loads |
| P2-F | Machine-flat coupon nail test (optional if already done) | No fingernail ridges |
| P2-G3 | G3 bar CAD 100.5 mm, machine-flat paths, MESH=0 start | X within **±0.20 mm** of 100 |
| P2-T0 | Log print_duration | Record T0 |
| P2-ZV | Zero-vision brain suggest-only through print | Journal clean, no crazy swings |
| P2-G4 | Later: 3× bar span ≤ 0.10 mm | Precision |

## Default every-print recipe

```gcode
FORGE_SET_Z_ADJUST Z=-0.480
FORGE_PRINT_START_ENV BED=65 EXTRUDER=214 SOAK=1 MESH=0
; MESH=0 loads golden profile (seconds)
; MESH=1 only if you need a quick 5×5 remap
```

## Files

- `forgeos_g3_machine_flat.gcode` — acceptance bar  
- `forgeos_machine_flat_coupon.gcode` — flat validation  
- `python3 -m forgeos.adaptive.service` — zero-vision brain  

## Status log

| Step | Result | Notes |
|------|--------|-------|
| P2-M golden mesh | **PASS** | Hot 7×7 dual-bed 65/65.5 · **137 s** · profile `default` SAVE_CONFIG |
| P2-G3 print | **RUNNING** | `forgeos_g3_phase2.gcode` · CAD 100.5 · MESH=0 · Z=−0.480 · machine-flat mono |
| P2-G3 measure X | pending | Pass if 100.00 ± 0.20 mm |
| P2-T0 min | pending | From print_duration when complete |
| P2-ZV brain | suggest-only | `python3 -m forgeos.adaptive.service` |
