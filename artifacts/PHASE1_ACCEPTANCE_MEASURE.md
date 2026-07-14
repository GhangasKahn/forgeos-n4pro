# Phase 1 Acceptance — Measure Card (G3 + T0)

**File:** `forgeos_g3_htpla_100mm_bar.gcode`  
**Bar CAD length (X):** **100.00 mm**  
**Bar size:** 100 × 10 × 5 mm · 0.2 mm layers · HTPLA recipe  

## Timeline (approx)

| Phase | Time |
|---|---|
| Dual-bed heat to ~62.6 °C | 3–8 min |
| Soak 6.6 min | 6.6 min |
| G28 + mesh | 5–12 min |
| Nozzle heat + print 25 layers | ~15–30 min |
| **Total wall clock** | **~35–60 min** |

## After print — wait until handleable, then measure

| Metric | Nominal | Measured | Error (meas − nom) |
|---|---|---|---|
| Length **X** (long axis) | 100.00 mm | ________ | ________ |
| Width **Y** | 10.00 mm | ________ | ________ |
| Height **Z** | 5.00 mm | ________ | ________ |

- [ ] First layer continuous? Y / N  
- [ ] Elephant foot estimate: ______ mm  
- [ ] Delam / holes / under-extrusion notes: ________________  
- [ ] Actual print duration from Mainsail (min): ______ → **T0**  
- [ ] Ambient T/RH during print: ______ / ______  

## Pass (G3)

|error| on 100 mm **≤ 0.20 mm** (aim ≤ 0.15 mm)

## Log T0 + dims

```bash
# example CSV then:
# axis,nominal_mm,measured_mm
# X,100.0,99.85
python3 scripts/import_caliper_csv.py measurements.csv
```

Tell the agent your measured X length + print minutes when done.
