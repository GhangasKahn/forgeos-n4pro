# Session handoff — Kyle + Grok (ForgeOS / Neptune 4 Pro)

**Saved:** 2026-07-14  
**Workspace:** `/Users/kylefetes/forgeos-n4pro`  
**Printer:** Elegoo Neptune 4 Pro · `znp-k1` · `192.168.1.178` · SSH `mks@192.168.1.178`  
**Purpose:** Resume this project without re-discovering context.

---

## How to resume with Grok next time

Paste something like:

> Resume ForgeOS from `SESSION_HANDOFF.md` and `configs/saved_state_shop_n4pro.yaml`.  
> Printer is at 192.168.1.178. Continue Phase 1 G3 bar measure / next steps.

Also run:

```bash
cd ~/forgeos-n4pro
python3 scripts/restore_saved_state.py   # re-apply Z/temps/stack after reboot
```

---

## What we built this session

### Greenfield project: **ForgeOS**
Not a port of OmniForge/legionforge (that tree was treated as forensic only).

**Repo:** `/Users/kylefetes/forgeos-n4pro`

| Area | Contents |
|---|---|
| Klipper overlays | dual-bed, env, Z, purge, retract/wipe, preflight, phase1 include |
| Materials | Protopasta HTPLA / HTPLA-CF + hardware packs |
| Stack | Wham Bam PEX + Brozzl plated copper 0.4 + HTPLA |
| Optim | multi-objective score, Bayesian 1D, simulated annealing |
| Environment | basement cold/humid homeostasis |
| Moisture soft-sensor | temp droop / heater power risk |
| Vision/ML plan | Jetson multi-cam + IR architecture + god-tier BOM |
| Tests | unit suite (30–35+ tests over session) |
| Deploy | live on printer `~/forgeos-n4pro` + `printer_data/config/forgeos/` |

### Live printer wiring
```text
printer.cfg includes:
  [include forgeos/forge_phase1.cfg]
```
That pulls safety, mesh, extrusion, moisture, macros, environment, firstlayer.

---

## Locked shop hardware (user confirmed)

| Item | Spec |
|---|---|
| Surface | **Wham Bam PEX** flex sheet |
| Nozzle | **Brozzl Plated Copper 0.4 mm** ([product](https://www.brozzl.com/products/plated-copper-nozzles/)) |
| Filament | **Protopasta HTPLA** (preferred brand) |
| Shop env | Basement-ish: cool + humid (profile ~14 °C / 65 % RH, open) |

---

## Process state to restore (machine-flat recalibration baseline)

**File:** `configs/saved_state_shop_n4pro.yaml`  
**JSON:** `artifacts/saved_state_shop_n4pro.json`  
**On printer:** `/home/mks/forgeos-n4pro/configs/saved_state_shop_n4pro.yaml`

| Param | Value |
|---|---|
| **Z adjust** | **−0.480 mm** (homing_origin Z, locked) |
| Bed | **65 °C** dual zone |
| Nozzle | **214 °C** |
| Soak | **5 min** |
| PA seed | **0.032** smooth 0.03 — recalibrate per material/nozzle/temp |
| Retract seed | **1.15 mm** @ 40 mm/s |
| Wipe | **1.4 mm** |
| Z-hop | **0.25 mm** |
| First layer | height **0.28**, width **0.44**, flow **100%**, **30 mm/s**, spacing ratio **1.00** |
| Purge | **`FORGE_PURGE`** in start macro |

The old pile-up bar result is historical, not acceptance evidence for this
machine-flat profile. Run `python3 scripts/calibrate.py next`; promote only
after dimensional and three-print repeatability gates pass.

### Z history (do not forget)
1. **−0.10** → empty bed / scrape (too low)  
2. **+0.08** → plastic sticks but **deep ribs**  
3. **+1.08** (+1 mm up) trial after fingernail-deep grooves  
4. Settled trial ~0.90 then operator **locked Z=−0.480** for G3 bar  

---

## Phase 1 status at save

| Gate / item | Status |
|---|---|
| G0 unit tests | PASS |
| G1 hardware ready | PASS |
| Dual-bed heat | PASS |
| Mesh | PASS (~0.19 mm p2p earlier) |
| Z-tune | Multiple runs; **locked** at Z=−0.480 |
| **G3 100 mm bar** | **Complete** reprint @ Z=−0.480 · X=**99–100 mm** · **G3 provisional** · T0≈21.6 min |
| G4/G5 | Not yet |
| Heartbeat monitor | Was running every 5 min in session |

### After bar cools — operator tasks
1. Caliper **long axis X** (nominal **100.00 mm**)  
2. Note print duration → **T0**  
3. Pass G3 if \|error\| ≤ **0.20 mm** (aim 0.15)  
4. Fill `artifacts/PHASE1_ACCEPTANCE_MEASURE.md`  

```bash
# optional import
python3 scripts/import_caliper_csv.py measurements.csv
```

---

## Important bugs fixed this session

1. **`TEMPERATURE_WAIT SENSOR=heater_bed_outer`** invalid → use `"heater_generic heater_bed_outer"` (was cancelling prints)  
2. Nested include `forgeos/forgeos/...` path bug  
3. Moonraker object names with spaces need URL encoding  
4. Cancel can hang during long soak/mesh → may need `systemctl restart klipper`  
5. OmniForge runtime spammed `OMNIFORGE_SHAPER` during mesh (stopped for coupons)  

---

## Key commands

### SSH / web
```bash
ssh mks@192.168.1.178
# use your local printer credentials (not stored in git)
open http://192.168.1.178/          # OmniForge UI if still served
open http://192.168.1.178:81/       # Mainsail
open http://192.168.1.178:7125/     # Moonraker
```

### Restore process knobs
```bash
cd ~/forgeos-n4pro && python3 scripts/restore_saved_state.py
```

### Deploy code
```bash
./scripts/deploy.sh --apply
# then RESTART klipper if overlays changed
```

### Useful macros
```gcode
FORGE_Z_STATUS
FORGE_BABY_UP / FORGE_BABY_DOWN
FORGE_PURGE
FORGE_SET_Z_ADJUST Z=-0.480
FORGE_PRINT_START_ENV BED=65 EXTRUDER=214 SOAK=5
```

### Gcodes on printer
- `forgeos_z_tune_square.gcode`  
- `forgeos_g3_htpla_100mm_bar_v2.gcode`  

---

## Docs index

| Doc | Topic |
|---|---|
| `SESSION_HANDOFF.md` | **This file** |
| `configs/saved_state_shop_n4pro.yaml` | Restorable process state |
| `docs/TESTING_SHEET.md` | All tests, times, metrics |
| `docs/STACK_PEX_BROZZL_PROTOPASTA.md` | Hardware stack |
| `docs/RETRACT_WIPE_OOZE.md` | Anti-whisker purge/retract |
| `docs/FIRST_LAYER_FIX.md` | Z / ribs / adhesion |
| `docs/VISION_ML_JETSON_STACK.md` | Multi-cam + Jetson architecture |
| `docs/BOM_GOD_TIER_VISION_RIG.md` | Full shopping list SKUs |
| `docs/environment_homeostasis.md` | Basement env control |
| `docs/zero_trust_gates.md` | G0–G7 gates |
| `artifacts/PHASE1_RESULTS.md` | Phase 1 live test results |
| `artifacts/PHASE1_ACCEPTANCE_MEASURE.md` | Measure card for bar |

---

## Vision / Jetson (planned, not fully hardware yet)

- Brain: **Jetson Orin Nano Super 8GB**  
- Cams: chamber + nozzle + oblique RGB  
- Thermal: MLX90640 / FLIR Lepton  
- **No LiDAR v1**  
- Code scaffold: `forgeos/vision/`, `configs/vision_rig.yaml`  
- Full BOM: `docs/BOM_GOD_TIER_VISION_RIG.md`  

---

## Conversation themes (for the human)

- Start from scratch elite OpenNeptune-class fork (ForgeOS)  
- Multi-objective: speed × precision × accuracy × quality  
- Zero-trust multi-gate verification before “god-tier / competitive” claims  
- Protopasta-only optimization path  
- Basement environment + moisture soft-sensor  
- First-layer struggle: Z low → empty; then ribs; Z raised; purge added  
- Vision/ML multi-view future with Jetson  
- Heartbeat every 5 minutes during long ops  

---

## Next session priorities (suggested)

1. Optional: remeasure X at 3 points → single mean (hard G3 if \|err\|≤0.20 mm)  
2. If hard pass → G4 (3×) or production jig; if short → flow/PA/shrink nudge  
3. Permanent `PROBE_CALIBRATE` / SAVE_CONFIG once Z is loved  
4. Order Jetson + cams from BOM when ready  
5. Disable or isolate legacy OmniForge services long-term  

---

## Git / local notes

- Project is under `/Users/kylefetes/forgeos-n4pro` with git history from Phase 0+  
- Printer copy may not be a full git remote — deploy via `scripts/deploy.sh`  
- Printer sudo password is local-only — do not commit secrets  

---

*End of handoff. Keep this file + saved_state YAML together.*
