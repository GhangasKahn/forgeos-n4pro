# Zero-vision path: $100 printer → $10k behavior

**No cameras. No Jetson required.**  
Everything here runs from **Moonraker telemetry + first-principles models** on any host that can reach the printer.

## What “$10k class” means here (without vision)

| Capability | Cheap default | ForgeOS zero-vision |
|------------|---------------|---------------------|
| Bed | One set-point, hope | **Dual-zone adaptive** inner/outer, bias learning |
| Nozzle | Fixed 214 °C | **Droop / power / moisture** adaptive target + speed |
| First layer | Manual babystep | Locked Z + **machine-flat volume** (s=w, f=1) |
| Solids | Zigzag + ironing | **Monotonic + Q-limited high speed**, zero ironing |
| Moisture | Ignore | **Soft-sensor risk** → derate |
| PA | Set once | Drift restore + material seed |
| Environment | Guess | Homeostasis bins (basement cold/humid) |
| Gates | Vibes | **G0–G7 zero-trust** |
| Control | Open loop | **2–4 Hz closed-loop brain** |

Vision later *adds* observations; it does not replace this stack.

## Architecture

```
Moonraker objects (temps, power, PA, Z, progress, mesh…)
        │  0.5 s ticks
        ▼
┌─────────────────── ZeroVisionBrain ───────────────────┐
│  DualBedController   — uniformity, outer bias EMA     │
│  NozzleThermal       — droop, power, moisture soft    │
│  Flat surface mode   — FORGE_FLAT first/solid/top     │
│  PA / flow / speed   — envelope-clamped nudges        │
│  precision_belief    — composite 0..1 “10k score”     │
└───────────────────────┬───────────────────────────────┘
                        │ suggest (default) or --arm
                        ▼
              Klipper gcode / macros
```

## Run (shop)

```bash
cd ~/forgeos-n4pro

# Safe: fully dynamic scoring + plans, no apply
python3 -m forgeos.adaptive.service --interval 0.5 -v

# After you trust it during a print:
python3 -m forgeos.adaptive.service --interval 0.5 --arm
```

Deploy macros (once):

```bash
rsync -avz klipper/overlays/forge_adaptive.cfg klipper/overlays/forge_phase1.cfg \
  mks@192.168.1.178:~/printer_data/config/forgeos/
# then FIRMWARE_RESTART when idle
```

## Dual-bed logic (precision)

Cold basement: outer ring loses heat faster → outer runs colder → warpage / first-layer delta.

Controller:

1. Measure `T_inner`, `T_outer`, powers  
2. EMA of delta  
3. Learn `outer_bias_c` (seed +1 °C)  
4. Command **independent** targets via  
   `SET_HEATER_TEMPERATURE HEATER=heater_bed` / `heater_bed_outer`  
5. Step ≤ 0.5 °C, interval ≥ 8 s, \|zone delta\| ≤ 4 °C  

Macro: `FORGE_ADAPT_DUAL_BED INNER=65 OUTER=66.5`

## Nozzle logic (accuracy under speed)

1. Droop EMA = target − actual  
2. If droop high + power high → **speed derate** (don’t starve melt)  
3. If droop high + headroom → **+1–2 °C** target (clamped 200–230)  
4. Moisture soft-sensor risk → further derate / small temp bump  
5. When stable → restore M220 and anneal target toward base 214  

## Machine-flat (no ironing)

Still the volume law: `flow × line_w = spacing`.  
Default pack: 0.44 / 1.00 / 1.00. Brain only **micro-trims flow**, never reintroduces pile-up spacing.

## Metrics logged every tick

| Key | Meaning |
|-----|---------|
| `precision_belief` | Composite 0..1 zero-vision “10k score” |
| `bed_uniform` | Dual-zone match |
| `nozzle_track` | Melt temperature tracking |
| `flat_volume` | Volume residual score |
| `moisture_risk` | Soft wetness risk |

Journal: `artifacts/zero_vision_journal.jsonl`  
State: `artifacts/zero_vision_state.json`

## Promotion path (still zero-trust)

1. Run brain **suggest-only** through a full print  
2. Inspect journal — no crazy temp swings  
3. `--arm` on a scrap coupon  
4. G3 bar measure \|err\| ≤ **0.10 mm** (CNC)  
5. G4×3 span ≤ **0.05 mm** + Cpk ≥ 1.0  
6. Only then claim shop pilot  

## What still needs hardware later (not required now)

- ADXL for better input shaper (you may already have profiles)  
- Enclosure / dryer for basement moisture  
- Vision for spaghetti/rib *images* (optional upgrade)

Until then, this zero-vision stack is the advanced path.
