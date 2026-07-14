# Calibration protocol (set up once)

## Safety
```text
FORGE_ARM via Python SafetyGate(purpose=campaign) + FORGE_ARM_AUTOTUNE only when intentional
```

## Sequence (`FORGE_CAL_FULL`)
1. `FORGE_PID_ALL`
2. `FORGE_SHAPER_CAL` (after ADXL/Eddy install)
3. `FORGE_PROBE_CAL` + SAVE_CONFIG
4. Dual bed heat + soak + `FORGE_MESH_PRECISION`
5. Flow coupon
6. PA pattern
7. 100 mm bar + 20 mm cube + hole coupon
8. Caliper CSV → `scripts/import_caliper_csv.py`
9. Optional anneal coupon → remeasure → update anneal scales

## Gates
- G3 on bar
- G4 on three bars
- G5 only after speed profile applied with G3/G4 still green
