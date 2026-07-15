# Session handoff — Kyle + Grok (ForgeOS / Neptune 4 Pro)

**Saved:** 2026-07-15 (mechanics-only god-tier refactor in progress)  
**Canonical worktree:** `/Users/kylefetes/forgeos-n4pro-cal`  
**Branch:** `cursor/calibration-suite-refactor-0319`  
**Mandate:** mechanics + physics + electronics + process control — **ZERO VISION**  
**Printer:** `znp-k1` · **192.168.1.178 only** · Host `n4pro` · mks  

---

## LIVE STATUS 2026-07-15

### Refactor (Phases 0–2 offline)

| Item | Status |
|---|---|
| Vision / computer_use / Jetson docs removed | **DONE** |
| requirements slimmed to PyYAML + pytest | **DONE** |
| `MoonrakerClient` upload/start/poll/snapshot | **DONE** |
| `forgeos/core/evidence.py` | **DONE** |
| `forgeos/calibration/ledger.py` (G2/G3/G4) | **DONE** |
| `gcode_for_test_id` + plan `cnc_close` | **DONE** |
| hub `cal` / `cnc` commands | **DONE** |
| pytest | **97 passed** · G0 pass |
| Hermes/swarm/film (master only) | not in cal tree; master still dirty with bulk |

### Live printer

| Item | Evidence |
|---|---|
| PRINTER_REAL | earlier wait_for_printer + SSH banner |
| Z lock | `homing_origin Z = -0.480` |
| Mesh G2 | p2p **0.195** ≤ 0.25 — `artifacts/mesh_loaded_20260715_104843.json` |
| G3 job | `forgeos_g3_cnc_campaign.gcode` SHA `dcd7b9ae…` uploaded |
| Print state | **paused** (print_duration ~344 s) — operator action required |
| G3 mean | **NOT YET** — need single caliper mean for CNC ≤0.10 |
| G4 | **NOT RUN** |

### Operator next

1. Inspect paused G3 job (bed clear? failure? intentional pause). Resume or cancel+reprint.  
2. After cool: caliper **one mean mm** on 100 mm X bar.  
3. `python3 scripts/run_calibration_suite.py analyze g3 --measured <MEAN>`  
4. G4 ×3 same process window → `analyze g4 --measurements a b c`  
5. Do **not** FIRMWARE_RESTART while a useful print is on the plate.

### Daily commands

```bash
cd /Users/kylefetes/forgeos-n4pro-cal
./scripts/forge_mac_hub.sh status|deploy|zt|g0|cal|cnc
python3 scripts/wait_for_printer.py --host 192.168.1.178 --max-wait 30
python3 scripts/restore_saved_state.py
```

### Cloud note

Cloud agents still cannot SSH to RFC1918 without a real tunnel (`docs/CLOUD_SSH_BRIDGE.md`). Mac LAN is the live path.

---

## Prior handoff content

# Session handoff — Kyle + Grok (ForgeOS / Neptune 4 Pro)

**Saved:** 2026-07-15 (live LAN campaign in progress)  
**Active worktree:** `/Users/kylefetes/forgeos-n4pro-cal`  
**Branch:** `cursor/calibration-suite-refactor-0319`  
**Printer:** Elegoo Neptune 4 Pro · `znp-k1` · **192.168.1.178 only** · SSH `mks@` / Host `n4pro`  
**Password (local only, never commit):** mks/makerbase  

---

## LIVE CAMPAIGN 2026-07-15 — status board

### Definition-of-done checklist (evidence only)

| Item | Status | Evidence |
|---|---|---|
| SSH ControlMaster `n4pro` | **PASS** | `ssh n4pro` → hostname `znp-k1`, user `mks` |
| `wait_for_printer.py` | **PASS** | `PRINTER_REAL` — SSH- banner + Moonraker JSON |
| `forge_mac_hub.sh status` | **PASS** | earlier session; Moonraker ready |
| Deploy + overlays on printer | **PASS** | `~/printer_data/config/forgeos/*` incl. `forge_calibration.cfg` |
| `printer.cfg` ForgeOS include | **PASS** | line 218: `[include forgeos/forge_phase1.cfg]`; backup `printer.cfg.bak.20260715104751` |
| Saved state restore; Z=−0.480 | **PASS** | `artifacts/live_restore_20260715_104814.json` — `homing_origin[2]=-0.48`; re-asserted before G3 start |
| Zero-trust atoms L0–L3 | **PASS** | `artifacts/zero_trust_live_report.json` — non-empty HTTP/SSH payloads |
| Zero-trust L4 ledger G3 | **FAIL (expected)** | historical range 99–100 mm → worst \|err\|=1.0 vs CNC 0.10; lies killed |
| pytest + G0 on Mac | **PASS** | 103 passed; G0 in L1 |
| Mesh G2 (loaded profile) | **PASS** | `artifacts/mesh_loaded_20260715_104843.json` — p2p **0.195** ≤ 0.25 |
| G3 CNC mean \|err\|≤0.10 | **IN PROGRESS** | print started; caliper mean not yet |
| G4 n≥3 span≤0.05 Cpk≥1.0 | **NOT RUN** | blocked on G3 mean |
| Cloud agent live SSH | **BLOCKED** | needs tunnel per `docs/CLOUD_SSH_BRIDGE.md` — Mac hub is daily path |

### Active print (Phase 6)

| Field | Value |
|---|---|
| Job | `forgeos_g3_cnc_campaign.gcode` |
| Remote | `~/printer_data/gcodes/forgeos_g3_cnc_campaign.gcode` |
| SHA256 | `dcd7b9ae2f8c1b7d64c73700dc90a9a7abe4b4d28b450a34241def7b7f15ad54` |
| Start | 2026-07-15 ~10:49 local |
| Stack | bed **65** / noz **214** / soak **5** / FL h=0.28 w=0.44 flow=1.00 spd=**18** fan=0 spacing=1.00 |
| Z | **−0.480** (do not reset) |
| PA in gcode | 0.0315 (stack); process target 0.030 re-applied via macros pre-start |
| Log | `artifacts/cal_run_log_20260715.jsonl` · status `artifacts/g3_print_status_20260715.json` |
| Meta | `artifacts/g3_job_meta_20260715.json` |

**Operator next (blocking CNC G3):** after cool, digital calipers on 100 mm X bar → **ONE mean mm** (not a range). Then:

```bash
cd /Users/kylefetes/forgeos-n4pro-cal
python3 scripts/run_calibration_suite.py analyze g3 --measured <MEAN>
# or
python3 scripts/zero_trust_live.py --host 192.168.1.178 --ssh-probe --g3-mean <MEAN>
```

Write `artifacts/g3_measure_20260715.json` with: mean_mm, n, caliper_id, ambient_c, operator, gcode sha, z_adjust, bed_c, nozzle_c, pa, verdict.

### Daily Mac path

```bash
cd /Users/kylefetes/forgeos-n4pro-cal   # or ~/forgeos-n4pro after merge
./scripts/forge_mac_hub.sh status|deploy|zt|open|sim
ssh n4pro 'hostname'
python3 scripts/wait_for_printer.py --host 192.168.1.178 --max-wait 30
```

### Explicit cloud note

Cloud agents still **cannot** reach `192.168.1.178` (RFC1918 SYN-sink). They need a **real** outbound tunnel (Tailscale / CF / reverse SSH) per `docs/CLOUD_SSH_BRIDGE.md`. On-LAN Mac hub does **not** need the bridge.

### Risks still open

- Moisture / draft on basement open machine
- Z drift if crash or mesh rewrite without re-verify
- G3 historical range lie already killed — need new mean only
- Do not run abrasive CF on Brozzl plated copper
- Do not confuse `local_cnc_bench` sim ALL_PASS with shop CNC PASS

---

## Prior handoff body (2026-07-14 and earlier)


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

## Process state to restore (GOOD ENOUGH baseline)

**File:** `configs/saved_state_shop_n4pro.yaml`  
**JSON:** `artifacts/saved_state_shop_n4pro.json`  
**On printer:** `/home/mks/forgeos-n4pro/configs/saved_state_shop_n4pro.yaml`

| Param | Value |
|---|---|
| **Z adjust** | **−0.480 mm** (homing_origin Z, locked) |
| Bed | **65 °C** dual zone |
| Nozzle | **214 °C** |
| Soak | **5 min** |
| PA | **0.030** smooth 0.03 |
| Retract | **1.20 mm** @ 40 mm/s |
| Wipe | **1.4 mm** |
| Z-hop | **0.25 mm** |
| First layer | width **0.58**, flow **114%**, ~**14–15 mm/s**, spacing ratio **0.84** |
| Purge | **`FORGE_PURGE`** in start macro |

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
| `docs/MACHINE_FLAT_ZERO_IRON.md` | Z / ribs / adhesion |
| `docs/VISION_ML_JETSON_STACK.md` | Multi-cam + Jetson architecture |
| `docs/VISION_ML_JETSON_STACK.md` | Full shopping list SKUs |
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
- Full BOM: `docs/VISION_ML_JETSON_STACK.md`  

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
