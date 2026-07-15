# Neptune 4 Pro calibration protocol

Calibration is a dependency graph, not a magic macro. Mechanical, heater,
probe and material measurements are specific to the physical printer. ForgeOS
therefore prepares safe commands and records evidence; it does not invent a Z
offset, flow ratio, pressure advance or input-shaper frequency.

## Run the suite

```bash
# Static configuration check; no printer connection
python3 scripts/calibrate.py audit

# Complete operator plan (24 tests)
python3 scripts/calibrate.py plan
python3 scripts/calibrate.py plan --phase one_time
python3 scripts/calibrate.py plan --phase fine_tuning

# Persistent evidence workflow (local state is gitignored)
python3 scripts/calibrate.py init
python3 scripts/calibrate.py next
python3 scripts/calibrate.py record safety-inspection pass \
  --evidence checklist=inspection-2026-07-15.pdf
python3 scripts/calibrate.py status
```

The recorder refuses to pass a test while dependencies are incomplete.
Conditional tests may be skipped only explicitly and with a reason. Skipping
input shaping is acceptable for basic printing when no accelerometer exists,
but it is not evidence for the maximum-quality/high-acceleration profile.

## One-time machine calibration

Run this after assembly or a firmware migration, and rerun only the portions
invalidated by hardware changes:

1. Electrical/thermal inspection and off-printer configuration backup.
2. Frame, V-wheels, toolhead, bed cable, belts and X-gantry mechanics.
3. Dual-Z gantry synchronization and heat-soaked bed-screw tramming.
4. Extruder `rotation_distance` by Klipper's 100 mm measure-and-trim method.
   Never tune X/Y/Z rotation distance from printed dimensions.
5. Hotend, inner-bed and outer-bed PID at representative temperatures.
6. Probe repeatability cold and heat-soaked (`PROBE_ACCURACY SAMPLES=10`).
7. Cold probe Z calibration, then delete/rebuild invalid old meshes.
8. Optional axis-twist compensation only when repeatable measured twist exists.
9. Heat-soaked 9×9 golden mesh; fix mechanics above 0.35 mm range.
10. Input shaper with a rigid accelerometer: X on toolhead, Y on moving bed.

Useful macros:

```text
FORGE_PROBE_ACCURACY
FORGE_PROBE_CAL
FORGE_MESH_PRECISION
FORGE_SHAPER_CAL
FORGE_CAL_STATUS
```

## Fine tuning

Repeat per material/nozzle/color/lot where the suite specifies:

1. Start with known-dry filament.
2. Temperature and first-layer uniformity.
3. Pressure advance at representative flow.
4. Coarse/fine flow ratio.
5. Sustainable volumetric flow; cap production at 80% of repeatable failure.
6. Retraction/wipe, then cooling, bridge and minimum-layer-time tests.
7. Three bars plus cube/hole coupon for shrinkage and hole compensation.
8. Speed/acceleration validation under both resonance and melt-flow ceilings.
9. Three cold-start repeats before promotion.
10. Optional anneal characterization from measured before/after coupons.

Do not use flow to hide a bad Z offset, use steps/mm to hide shrinkage, or use
ironing to hide excess top-surface volume.

## Promotion gates

- G3: `|mean error| <= 0.20 mm` on 100 mm and no visual hard fail.
- G4: three-print dimensional span `<= 0.10 mm`.
- G5: speed profile retains G3/G4 and has zero skipped steps.
- Annealed claims require measured post-anneal scales from three coupons.

## Primary references

- [OpenNept4une printer calibration](https://github.com/OpenNeptune3D/OpenNept4une/wiki/Printer-Calibration-%E2%80%90-Klipper-%26-OrcaSlicer)
- [Klipper rotation distance](https://www.klipper3d.org/Rotation_Distance.html)
- [Klipper probe calibration](https://www.klipper3d.org/Probe_Calibrate.html)
- [Klipper bed mesh](https://www.klipper3d.org/Bed_Mesh.html)
- [Klipper resonance compensation](https://www.klipper3d.org/Resonance_Compensation.html)
- [Klipper measuring resonances](https://www.klipper3d.org/Measuring_Resonances.html)
- [Klipper pressure advance](https://www.klipper3d.org/Pressure_Advance.html)
- [Ellis' print tuning guide](https://ellis3dp.com/Print-Tuning-Guide/)
