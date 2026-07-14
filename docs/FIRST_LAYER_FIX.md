# First-layer fix: adhesion + stringing (Phase 1)

## What you saw

| Symptom | Likely cause |
|---|---|
| Poor bed adhesion / lifts | Nozzle **too high** (Z not dialed) and/or cold basement + dirty PEI |
| Stringy / lifts into strings | High nozzle + long un-retracted travels + temp a bit hot + weak first squish |
| Z “not set properly” | Probe `z_offset: 1.275` is only a seed; live paper/babystep not locked for HTPLA |

## Fix stack (do in order)

### 1. Bed prep (2 min)
- Wash PEI with **IPA** (or warm water + dish soap if greasy), dry fully  
- Optional: thin **glue stick** for HTPLA in cold basements  
- No drafts on first layer (box fan / HVAC away from printer)

### 2. Set live Z closer to bed
In Mainsail console **before** reprint:

```gcode
FORGE_SET_Z_ADJUST Z=-0.10
FORGE_Z_STATUS
```

- **More negative** = closer = more squish (if still high/stringy)  
- **Less negative / positive** = higher (if scraping)

### 3. Z-tune square first (~10–15 min including soak)
Print `forgeos_z_tune_square.gcode`. While first layer lays:

```gcode
FORGE_BABY_DOWN   ; if lines are round, not stuck, stringy bridges
FORGE_BABY_UP     ; if rough, translucent, nozzle digs
```

Target: lines **slightly squished**, stuck hard, no gaps between lines.

Then:

```gcode
FORGE_Z_STATUS
```

Write down the value (e.g. `-0.12`).

### 4. Print improved G3 bar
`forgeos_g3_htpla_100mm_bar_v2.gcode` includes:
- hotter bed **65 °C**, nozzle **215 °C** (less string than 217–220 for some HTPLA)
- **brim**
- **0.28 mm** first layer, **18 mm/s**, flow bump
- stronger **retract 1.0 mm**
- fan off until layer 3

### 5. Optional: stop OmniForge runtime during coupons
It was spamming shaper commands mid-mesh:

```bash
ssh mks@192.168.1.178 'echo makerbase | sudo -S systemctl stop omniforge-runtime'
```

## Permanent probe calibration (later)
After good live Z, run paper test + `PROBE_CALIBRATE` / `SAVE_CONFIG` so `z_offset` in printer.cfg matches reality (replaces babystep dependence).

## Ribbed / piled rows (not a flat sheet)

**God-tier flat rule:** lines **side by side** — `step ≈ line_width` (`spacing_ratio = 1.0`), flow ≈ **1.0**.  
Do **not** stack heavy overlap (old 0.58w / 0.84 step / 114% pile-up pack). See `docs/FLAT_FIRST_LAYER.md`.

| Cause | Fix |
|---|---|
| Heavy overlap / raised ridges | `spacing_ratio=1.0`, line_w≈**0.44**, flow **1.00** |
| Tiny gaps between lines | ratio **0.97–0.98** or flow **1.02–1.04** only |
| Melt too cool (plated copper) | Nozzle **214 °C** so edges weld without pile |
| Z a hair high (round beads) | One click `FORGE_BABY_DOWN` |
| Too fast | First layer **12 mm/s** |

v6 bar / v3 z-tune use the flat pack. Piles → less overlap; gaps → tiny ratio cut, not 0.84 pile.
