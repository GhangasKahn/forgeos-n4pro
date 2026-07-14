# Filament moisture detection without a dryer sensor

## Short answer

You **cannot** get a true lab moisture % from “nozzle got colder” alone.  
You **can** build a **soft-sensor risk score** from hotend thermal load while extruding, then **automate outflow** (flow / temp / speed) conservatively.

True RH-in-filament needs either:

- a **filament dryer with humidity probe**, or  
- industrial moisture analyzers / weight-loss tests  

ForgeOS implements the soft-sensor path so the printer reacts even if you never dry.

---

## Physics (why temperature falls)

When filament enters the melt zone:

1. **Sensible heat** — heat solid plastic up to melt temperature  
2. **Melt enthalpy** — solid → liquid polymer  
3. **If wet:** water flashes to steam (**latent heat ≈ 2250 J/g**)  

That third term steals heater budget. Under the same volumetric flow you often see:

| Signal | Wet tendency |
|---|---|
| `target - temperature` (droop) | **Increases** |
| Heater PWM / `extruder.power` | **Increases** to hold set-point |
| Short-term temp variance | **Increases** (boil / sputter) |
| Extruded bead | bubbles, zits, hissing, weak layers, inconsistent width |

So: **droop + heater power + variance** under known flow ≈ moisture **risk**, not %H₂O.

### Confounders (must respect — zero trust)

These look “wet” too:

- flow too high for the heater  
- partial clog / ground filament  
- bad PID / failing heater cartridge  
- aggressive part-cooling on the block  
- CF / metal fill changing thermal mass  
- first layers vs long steady extrusion  

Always prefer **relative-to-dry-baseline** scoring over absolute thresholds.

---

## How ForgeOS models it

Module: `forgeos/sensors/moisture_soft_sensor.py`

```text
observe(temp, target, power?, flow, is_extruding, known_dry?)
   → EMA droop / power
   → risk ∈ [0,1]  level ∈ {dry, mild, moderate, severe}
   → recommend_response() → temp Δ, flow mult, speed derate, gcode
```

### Learning a dry baseline

1. Print a short purge/wall with filament you trust (or just after a real dry).  
2. Feed samples with `known_dry=True`.  
3. Later spools are scored as **excess droop/power vs that baseline** at similar flow.

### Automated outflow / process response

| Level | Nozzle temp | Flow (M221) | Speed | Notes |
|---|---|---|---|---|
| dry | — | — | — | no action |
| mild | +3 °C | unchanged | ×0.92 | small derate |
| moderate | +6 °C | ×1.03 | ×0.80 | tiny +flow for under-extrusion |
| severe | +8 °C | ×1.02 | ×0.65 | **PAUSE** + dry spool |

Why not “just push more filament” when wet?

Steam already occupies volume. Dumping more plastic often makes **blobs and voids**, not CNC accuracy.  
**Slow + slightly hotter** improves melt consistency; flow bumps stay tiny and envelope-clamped.

---

## Wiring to the live printer (Moonraker)

Poll while printing:

```text
GET /printer/objects/query?extruder&toolhead&print_stats
```

Useful fields:

- `extruder.temperature`, `extruder.target`, `extruder.power`  
- extrusion activity from `print_stats` / gcode state  
- estimate `volumetric_flow` from slicer metadata or E-speed × π(d/2)²  

Guardian loop (future Phase 1+):

1. Sample every 1–2 s while `printing`  
2. `sensor.observe(...)`  
3. If level changes → journal event  
4. If `runtime_micro` armed → apply gcode **through SafetyGate clamps**  
5. If severe → pause + Mainsail message  

Default: **observe + alert only** until you arm automation.

---

## Hardware upgrades (optional, better than soft-sensor alone)

| Hardware | Benefit |
|---|---|
| Dryer with RH display | Ground truth for soft-sensor calibration |
| Enclosure ambient/RH | Shop humidity context |
| Inline filament dry path | Prevention > detection |
| Load cell / filament scale | Mass consistency (advanced) |

For Protopasta HTPLA-CF, drying is still the correct engineering control. Soft-sensor is **damage control + detection**, not a substitute for dry filament on precision fixtures.

---

## Zero-trust gate note

Moisture automation must **not** defeat G3/G4 accuracy gates.  
Any auto flow/temp change is journaled; coupons re-validate after policy changes.
