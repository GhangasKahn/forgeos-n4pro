"""Full calibration suite documentation — Neptune 4 Pro GOD-TIER prints."""

# ForgeOS Calibration Suite

Complete one-time setup and fine-tuning catalog for the **Elegoo Neptune 4 Pro** (`znp-k1`), aligned with [OpenNeptune3D calibration macros](https://github.com/OpenNeptune3D/OpenNept4une/wiki/Printer-Calibration-%E2%80%90-Klipper-%26-OrcaSlicer) and ForgeOS zero-trust gates (G0–G7).

## Quick commands

```bash
# List all tests
python3 scripts/run_calibration_suite.py list

# Plan durations and prerequisites
python3 scripts/run_calibration_suite.py plan one_time
python3 scripts/run_calibration_suite.py plan fine_tune
python3 scripts/run_calibration_suite.py plan full

# Analyze measurements (offline)
python3 scripts/run_calibration_suite.py analyze g3 --measured 99.92
python3 scripts/run_calibration_suite.py analyze g4 --measurements 100.0 100.04 99.98
python3 scripts/run_calibration_suite.py analyze pa --height 8.0
python3 scripts/run_calibration_suite.py analyze flow --wall 0.43 --line 0.44
python3 scripts/run_calibration_suite.py analyze mesh --p2p 0.19

# Generate calibration G-code
python3 scripts/run_calibration_suite.py gcode flow_cube -o artifacts/gcodes/flow_cube.gcode
python3 scripts/run_calibration_suite.py gcode first_layer -o artifacts/gcodes/first_layer.gcode

# Live printer (dry-run first)
python3 scripts/run_calibration_suite.py live one_time --host 192.168.1.178 --dry-run
```

## One-time calibration (hardware install / major change)

| ID | Macro | OpenNeptune | Duration |
|---|---|---|---|
| `pid_extruder` | `FORGE_PID_EXTRUDER` | `PID_TUNE_EXTRUDER` | ~15 min |
| `pid_bed_inner` | `FORGE_PID_BED_INNER` | `PID_TUNE_BED` | ~15 min |
| `pid_bed_outer` | `FORGE_PID_BED_OUTER` | `PID_TUNE_OUTER_BED` | ~15 min |
| `probe_z_offset` | `FORGE_PROBE_CAL` | `CALIBRATE_PROBE_Z_OFFSET` | ~10 min |
| `bed_screws_tilt` | `FORGE_SCREWS_TILT` | `BED_LEVEL_SCREWS_TUNE` | ~15 min |
| `axis_twist` | `FORGE_AXIS_TWIST` | `AXIS_TWIST_COMP_TUNE` | ~20 min |
| `rotation_distance` | `FORGE_ROTATION_DISTANCE` | manual | ~10 min |
| `input_shaper` | `FORGE_SHAPER_CAL RUN=1` | `SHAPER_CALIBRATE` | ~20 min (needs ADXL) |
| `mesh_golden` | `FORGE_MESH_PRECISION` | `AUTO_FULL_BED_LEVEL` | ~25 min |

**Critical order:** screws tilt → **always** re-run probe Z offset → hot dual-bed soak → precision mesh.

## Fine-tuning (per material / session)

| ID | Purpose | Pass criteria |
|---|---|---|
| `z_offset_live` | First-layer squish | Continuous lines, no scrape |
| `first_layer_squish` | Single-layer panel | Adhesion without elephant foot |
| `flow_rate` | Single-wall cube | 95–105% of line width |
| `pressure_advance` | PA tower | PA in 0.02–0.12 typical |
| `temperature_tower` | Nozzle temp | Best surface/bridge layer |
| `retraction_distance` | Stringing control | Cleanest tower layer |
| `speed_accel` | Motion limits | No ringing (needs shaper) |
| `mesh_fast` | Production mesh | p2p ≤ 0.80 mm |

## Gate verification (zero-trust)

| Gate | Test ID | Metric |
|---|---|---|
| G3 | `dimensional_accuracy` | \|error\| ≤ 0.20 mm / 100 mm |
| G4 | `precision_replicate` | 3× span ≤ 0.10 mm |
| G5 | `speed_regression` | ≥25% faster than T0, G3 holds |
| G6 | `anneal_dimensional` | Post-anneal dims in band |
| G7 | `reliability_soak` | ≥2 h, 0 MCU losses |

## Klipper macros

New overlay: `klipper/overlays/forge_calibration.cfg` (included from `forge_phase1.cfg`).

Operator status macro: `FORGE_CAL_STATUS`

## Python API

```python
from forgeos.calibration import CalibrationRunner, analyze_mesh_matrix, test_by_id

runner = CalibrationRunner()
print(runner.plan_report("full"))

analysis = analyze_mesh_matrix(probed_matrix)
runner.record_measurement("dimensional_accuracy", {"measured_mm": 99.95})
```

## Research references

- Elegoo Neptune 4 Pro manual: 36-point auto level, paper Z-offset, auxiliary corner screws
- OpenNeptune3D: PID macros, probe Z, screws tilt, axis twist, adaptive mesh
- Klipper: `TUNING_TOWER` for PA/temp, `SHAPER_CALIBRATE`, `PROBE_CALIBRATE`
- ForgeOS: dual-bed soak, PEX+Brozzl+HTPLA stack, machine-flat coupons

See also: [calibration_protocol.md](calibration_protocol.md), [TESTING_SHEET.md](TESTING_SHEET.md), [zero_trust_gates.md](zero_trust_gates.md).
