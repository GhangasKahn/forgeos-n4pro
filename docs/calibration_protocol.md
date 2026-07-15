# Calibration protocol (set up once)

See **[CALIBRATION_SUITE.md](CALIBRATION_SUITE.md)** for the full catalog, CLI, and analysis tools.

## Safety
```text
FORGE_ARM via Python SafetyGate(purpose=campaign) + FORGE_ARM_AUTOTUNE only when intentional
```

## Sequence (`FORGE_CAL_FULL` / `python3 scripts/run_calibration_suite.py plan full`)
1. `FORGE_PID_ALL` (or per-zone `FORGE_PID_*`)
2. `FORGE_SHAPER_CAL RUN=1` (after ADXL/Eddy install)
3. `FORGE_PROBE_CAL` + SAVE_CONFIG
4. `FORGE_SCREWS_TILT` → **re-run** `FORGE_PROBE_CAL`
5. Dual bed heat + soak + `FORGE_MESH_PRECISION`
6. `FORGE_ROTATION_DISTANCE` (if extrusion inaccurate)
7. Flow coupon (`run_calibration_suite.py gcode flow_cube`)
8. `FORGE_PA_CAL` + PA tower print
9. 100 mm bar + 20 mm cube + hole coupon
10. Caliper CSV → `scripts/import_caliper_csv.py`
11. Optional anneal coupon → remeasure → update anneal scales

## Gates
- G3 on bar — `run_calibration_suite.py analyze g3 --measured <mm>`
- G4 on three bars — `analyze g4 --measurements ...`
- G5 only after speed profile applied with G3/G4 still green
