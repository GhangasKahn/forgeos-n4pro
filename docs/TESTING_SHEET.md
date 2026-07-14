# ForgeOS Testing Sheet — Neptune 4 Pro + Protopasta

**Machine:** Elegoo Neptune 4 Pro (`znp-k1` / `192.168.1.178`)  
**Materials focus:** Protopasta HTPLA / HTPLA-CF  
**Targets:** SPEED × PRECISION × ACCURACY × QUALITY (fixture-grade)  
**Environment default:** basement ~14 °C / ~65 % RH / open frame  

Use this sheet as a runbook. Check boxes as you go. Log numbers in the **Capture** column or the journal (`artifacts/phase1_journal.sqlite3` / later production journal).

---

## How to use

1. Run tests **in order** when possible (later gates depend on earlier ones).  
2. Record **wall-clock start/end** for every timed test.  
3. Do not mark a gate **PASS** without the listed metrics filled in.  
4. Heartbeat monitor (every ~5 min) is separate — it does **not** replace these tests.

**Legend**

| Symbol | Meaning |
|---|---|
| ⏱ | Approx duration (operator + machine) |
| 🧪 | Exact procedure |
| 📊 | Analysis / data to capture |
| ✅ | Pass criteria |

---

# SECTION A — Software & gates (no filament required)

## A0 · Local unit suite (G0 core)

| | |
|---|---|
| **⏱ Duration** | **2–5 min** |
| **When** | Every code change; start of any test day |
| **Command** | `cd ~/forgeos-n4pro && python3 -m pytest -q && python3 scripts/run_g0_gate.py` |

**🧪 What is done**  
Runs automated unit tests for materials, safety envelopes, multi-objective scoring, moisture soft-sensor, environment/homeostasis, campaigns, journal.

**📊 Capture**  
- [ ] pytest result: `___ / ___` passed  
- [ ] G0 gate status: PASS / FAIL  
- [ ] Commit/hash under test: `__________`

**✅ Pass**  
All tests green; G0 = pass.

---

## A1 · Deploy + config integrity

| | |
|---|---|
| **⏱ Duration** | **5–10 min** |
| **When** | After code changes you want on the printer |
| **Command** | `./scripts/deploy.sh --apply` then confirm include |

**🧪 What is done**  
Rsync ForgeOS to printer; ensure `printer.cfg` includes `forgeos/forge_phase1.cfg`; Klipper restart/reload; list FORGE macros.

**📊 Capture**  
- [ ] Deploy time / backup path: `__________`  
- [ ] Printer state after restart: ready / error  
- [ ] FORGE macro count (expect ~30+): `___`  
- [ ] Any config error message: `__________`

**✅ Pass**  
`state=ready`; FORGE macros present; no include errors.

---

## A2 · Live heartbeat / stall watch (ongoing)

| | |
|---|---|
| **⏱ Duration** | Continuous; pulse every **~5 min** |
| **When** | During long sessions / unattended blocks |
| **How** | Session monitor (already configured) or re-enable if needed |

**🧪 What is done**  
Poll Moonraker: printer state, print state, nozzle/bed/outer temps, homed axes, idle state.

**📊 Capture (per pulse or daily log)**  
- [ ] Last OK heartbeat time: `__________`  
- [ ] Any FAIL/CHECK events: `__________`  
- [ ] Unexpected MCU loss / shutdown: Y / N  

**✅ Pass**  
No silent multi-pulse failures; ready or intentional printing.

---

## A3 · G1 · Hardware preflight (live)

| | |
|---|---|
| **⏱ Duration** | **1–3 min** |
| **Command** | `python3 scripts/phase1_live_tests.py --host 192.168.1.178` |

**🧪 What is done**  
Confirms Moonraker reachable, Klipper **ready**, basic object query, disk headroom policy, G0+G1 gates. **No motion, no heat** by default.

**📊 Capture**  
- [ ] G1: PASS / FAIL  
- [ ] State message: `__________`  
- [ ] Report path: `artifacts/phase1_report.json`  

**✅ Pass**  
G0 + G1 both true.

---

# SECTION B — Thermal, mesh, environment (no print required)

## B1 · Dual-bed heat + soak smoke

| | |
|---|---|
| **⏱ Duration** | **Heat 3–8 min** (from cold) + **soak 1–7 min** = **~5–15 min** total  
| **Typical Phase 1 smoke** | Bed 60 °C, soak **2 min** → ~**6–10 min** from cold basement  
| **Full basement recipe** | Bed ~62.6 °C, soak **~6.6 min** → **~12–20 min** from cold  
| **Command (smoke)** | `python3 -u scripts/phase1_live_tests.py --host 192.168.1.178 --heat --bed 60 --soak-min 2` |

**🧪 What is done**  
1. Set **inner** `heater_bed` and **outer** `heater_bed_outer` targets.  
2. Poll until both near target.  
3. Hold soak (thermal equalization for dual zones + cold basement).  
4. Cool heaters unless mesh follows.

**📊 Capture**  
- [ ] Ambient shop T/RH: `___ °C` / `___ %`  
- [ ] Time to reach target (inner/outer): `___ / ___ min`  
- [ ] Temp at start of soak: inner `___` outer `___`  
- [ ] Temp at end of soak: inner `___` outer `___`  
- [ ] Max |inner−outer| during soak: `___ °C`  
- [ ] Heater power at hold (if logged): inner `___` outer `___`  
- [ ] Any thermal runaway / fault: Y / N  

**✅ Pass**  
Both zones within ~±2–3 °C of target after soak; no faults; outer tracks (dual-bed working).

**Why it matters**  
Cold basements + dual zones → first-layer adhesion and mesh truth. Soak length is a **speed vs quality** trade (failed first layers cost more time than a longer soak).

---

## B2 · Home + bed mesh map

| | |
|---|---|
| **⏱ Duration** | **G28 ~0.5–1.5 min** + **mesh ~4–12 min** = **~5–15 min**  
| **Observed Phase 1** | Full G28+mesh completed; ~11×11 class density → on order of **~8–12 min**  
| **Command** | `python3 -u scripts/phase1_live_tests.py --host 192.168.1.178 --mesh`  
| **Note** | Prefer mesh **after** bed is at print temp + soak for “hot mesh” truth (adds B1 time). Cold mesh is faster but less accurate for real prints. |

**🧪 What is done**  
1. `G28` home all axes.  
2. `BED_MESH_CALIBRATE` across configured grid.  
3. Read probed matrix; compute peak-to-peak.

**📊 Capture**  
- [ ] Mesh at temp? cold / hot (`___ °C` bed)  
- [ ] Probe count / points: `___` (Phase 1 live: **121** points)  
- [ ] Min Z: `___ mm`  Max Z: `___ mm`  
- [ ] **Peak-to-peak (p2p):** `___ mm` (Phase 1: **0.193 mm**)  
- [ ] Profile name saved: `__________`  
- [ ] Failed probe samples / retries noticed: Y / N  
- [ ] Homed axes after: `__________`  

**✅ Pass (Phase 1 / G2 mesh portion)**  
p2p **≤ 0.80 mm** hard fail threshold; **≤ 0.40 mm** preferred; **≤ 0.25 mm** excellent for fixtures.

**Why it matters**  
Accuracy of first layer and dimensional Z consistency. High p2p → re-level / mechanical issue before chasing slicer settings.

---

## B3 · Environment session plan (software only)

| | |
|---|---|
| **⏱ Duration** | **1 min** |
| **Command** | `python3 scripts/env_plan.py --profile environments/basement_default.yaml` |

**🧪 What is done**  
Compute before/during/after plans for ambient bin (basement cold_humid, enclosure, etc.).

**📊 Capture**  
- [ ] Env bin: `__________`  
- [ ] BEFORE bed / nozzle / soak: `___` / `___` / `___ min`  
- [ ] DURING speed factor / fan %: `___` / `___`  
- [ ] AFTER cool style: staged / passive / hold_warm  
- [ ] Moisture prior: `___`  

**✅ Pass**  
Plan generates; soak increases when colder/wetter; enclosure changes speed/soak sanely.

---

## B4 · FORGE macro smoke (operator path)

| | |
|---|---|
| **⏱ Duration** | **2–5 min** |
| **Where** | Mainsail console or scripted gcode |

**🧪 Exact sequence**  
```gcode
FORGE_SET_AMBIENT TEMP=14 RH=65 DRAFT=0.3
FORGE_SET_ENCLOSURE MODE=open
FORGE_SET_NOZZLE TYPE=hardened DIA=0.4
FORGE_SET_MATERIAL SKU=protopasta_htpla
FORGE_PREFLIGHT
FORGE_ENV_STATUS
FORGE_APPLY_ENV_TARGETS BED=62.6 NOZ=216.7 SOAK=6.6
FORGE_MOISTURE_STATUS
```

**📊 Capture**  
- [ ] Each command OK / error  
- [ ] PREFLIGHT pass (hardened + HTPLA)  
- [ ] CF preflight fail test (optional): set CF + brass → must error  

**✅ Pass**  
All OK; abrasive+soft nozzle hard-fails when tested.

---

## B5 · Moisture soft-sensor dry baseline (optional, short extrusion)

| | |
|---|---|
| **⏱ Duration** | **5–15 min** (purge/line extrusion at temp) |
| **Needs** | Filament loaded; prefer known-dry or just-dried spool |

**🧪 What is done**  
Heat nozzle to recipe temp; extrude steady line/purge while logging `extruder.temperature`, `target`, `power`, estimated volumetric flow; mark samples `known_dry=True` once.

**📊 Capture**  
- [ ] Baseline droop °C: `___`  
- [ ] Baseline heater power 0–1: `___`  
- [ ] Flow mm³/s used: `___`  
- [ ] Risk score on dry spool: `___` (expect low)  

**✅ Pass**  
Dry risk stays in `dry`/`mild`; sensor returns stable EMA.

**Why it matters**  
Later “wet” detection is relative to this baseline (basement humidity prior alone is not enough).

---

# SECTION C — Print coupons (filament required)

## C1 · G3 · Accuracy coupon (100 mm bar) — **Phase 1 completion print**

| | |
|---|---|
| **⏱ Duration** | **Setup 10–15 min** + **print ~20–45 min** (role-based profile; depends on height/infill) + **measure 5 min** ≈ **~40–70 min** total  
| **Material** | Protopasta HTPLA (start here; CF later)  
| **Nozzle** | Hardened 0.4 mm OK for pure HTPLA |

**🧪 Exact test**  
1. Set ambient: `FORGE_SET_AMBIENT` + `FORGE_SET_ENCLOSURE`.  
2. Apply env targets (or `FORGE_PRINT_START_ENV`).  
3. Dual-bed heat + soak (full basement soak if cold).  
4. Hot mesh (recommended) or load last good mesh.  
5. Print **100.00 mm XY bar** (+ optional 20 mm cube / hole).  
6. Cool staged if basement cold (`FORGE_PRINT_END_ENV`).  
7. Caliper measure after cool-to-handle (or full ambient cool for tight metrology).

**📊 Capture (required)**  

| Metric | Nominal | Measured | Error |
|---|---|---|---|
| Bar X length | 100.00 mm | ___ | ___ |
| Bar Y length (if 2D) | 100.00 mm | ___ | ___ |
| Bar width | ___ | ___ | ___ |
| Height (if relevant) | ___ | ___ | ___ |
| Hole Ø (if printed) | ___ | ___ | ___ |

Also:  
- [ ] Wall-clock print time (slicer estimate vs actual): `___ / ___ min` → this seeds **T0**  
- [ ] First layer: continuous? Y / N  
- [ ] Elephant foot estimate: `___ mm`  
- [ ] Delam / cracks / under-extrusion notes: `__________`  
- [ ] Nozzle/bed used: `___ / ___ °C`  
- [ ] Mesh p2p that print used: `___ mm`  
- [ ] Ambient T/RH: `___ / ___`  

**✅ Pass (G3)**  
\|error\| on 100 mm span **≤ 0.20 mm** (aim **≤ 0.15 mm**).  
First layer not critically failed.

**Analysis intent**  
Separates **machine scale/flow** error from **environment** and **speed** effects. Feeds dimensional fit (`import_caliper_csv.py`) → xy_scale / flow updates.

---

## C2 · G4 · Precision (repeatability) — 3× same coupon

| | |
|---|---|
| **⏱ Duration** | **3 × (C1 print)** ≈ **~1.5–3.5 hours** machine time + measure  
| **Do not change** | G-code, filament lot, nozzle, ambient profile if possible |

**🧪 Exact test**  
Print the **same** 100 mm bar gcode three times back-to-back (or same day). Measure each.

**📊 Capture**  

| Run | X meas | Error | Print time |
|---|---|---|---|
| 1 | ___ | ___ | ___ |
| 2 | ___ | ___ | ___ |
| 3 | ___ | ___ | ___ |

- [ ] Span = max(meas) − min(meas): `___ mm`  
- [ ] Mean error: `___ mm`  

**✅ Pass (G4)**  
Span **≤ 0.10 mm** on 100 mm feature.

**Analysis intent**  
**Precision ≠ accuracy.** Tight span with offset → systematic scale fix. Wide span → mechanical play, temp drift, moisture, or process instability.

---

## C3 · T0 cycle-time baseline (paired with C1)

| | |
|---|---|
| **⏱ Duration** | Included in C1  
| **Definition** | Actual wall-clock from `PRINT_START`/`printing` → `complete` for the **standard fixture coupon** |

**📊 Capture**  
- [ ] T0 actual minutes: `___`  
- [ ] Slicer estimate minutes: `___`  
- [ ] Profile name (balanced / speed / accuracy): `__________`  
- [ ] G-code filename: `__________`  

**✅ Pass**  
T0 logged once under known-good G3 print. Later G5 compares against this T0.

---

## C4 · G5 · Speed trial (same coupon, faster pack)

| | |
|---|---|
| **⏱ Duration** | **1 print** ≈ **15–40 min** (should be **≥25% faster** than T0 if successful) + measure  
| **Prereq** | G3 (and ideally G4) already established |

**🧪 Exact test**  
1. Apply `max_speed_feasible` / higher role speeds / higher accel **only if** shaper exists or stay within known safe accel.  
2. Same coupon geometry.  
3. Measure dims + quality rubric.

**📊 Capture**  
- [ ] Time: `___ min`  vs T0 `___` → improvement `% = (T0−T)/T0`  
- [ ] Dim error 100 mm: `___`  
- [ ] First layer / surface / delam: pass / fail  
- [ ] Multi-objective J (if computed): `___`  

**✅ Pass (G5)**  
Time improvement **≥ 25%** vs T0 **and** G3 still holds **and** no critical quality fail.

**Analysis intent**  
Proves speed gains are on the **feasible Pareto front**, not “fast and wrong.”

---

## C5 · HTPLA-CF abrasive path (after HTPLA baseline)

| | |
|---|---|
| **⏱ Duration** | Same as C1 class **~40–70 min** first coupon  
| **Prereq** | Hardened nozzle **≥ 0.5–0.6 mm**; brass = auto fail |

**🧪 Exact test**  
`FORGE_SET_MATERIAL SKU=protopasta_htpla_cf` + nozzle checks; print coupon; lower volumetric flow.

**📊 Capture**  
- [ ] Nozzle type/dia: `__________`  
- [ ] PREFLIGHT: PASS / FAIL  
- [ ] Clog/skip events: Y / N  
- [ ] Dim error / surface / fiber roughness notes  

**✅ Pass**  
PREFLIGHT enforces hardened nozzle; printable coupon without clogs; dims in band if claiming fixture use.

---

## C6 · G6 · Anneal dimensional loop (HTPLA process anneal)

| | |
|---|---|
| **⏱ Duration** | Print coupon **~30–50 min** + oven **~60 min hold** + cool **30–60 min** + measure ≈ **~2.5–4 hours** wall  
| **Oven** | ~110 °C, ~60 min (verify with oven thermometer) |

**🧪 Exact test**  
1. Print gauge set with **pre-scale** from material pack (xy_scale seed).  
2. Measure green (pre-anneal).  
3. Anneal per Protopasta HTPLA protocol.  
4. Measure post-anneal.  
5. Update shrink matrix / hole compensation.

**📊 Capture**  

| Feature | CAD | Pre-anneal | Post-anneal | Post error |
|---|---|---|---|---|
| 100 mm bar | 100 | ___ | ___ | ___ |
| Hole | ___ | ___ | ___ | ___ |

- [ ] Observed XY shrink %: `___`  
- [ ] Z change %: `___`  
- [ ] Warpage notes: `__________`  

**✅ Pass (G6)**  
Post-anneal critical dims within **±0.20 mm** (or stated fixture tolerance) **with** compensation applied on reprint.

**Analysis intent**  
Separates **print error** from **crystallization shrink**. Required for heat-resistant jigs that see shop heat or friction.

---

# SECTION D — Sensors, learning, reliability

## D1 · G2 · Input shaper / ADXL (or Eddy/Beacon)

| | |
|---|---|
| **⏱ Duration** | Install hardware **30–90 min** first time; cal run **10–20 min**  
| **When** | Phase 2 |

**🧪 What is done**  
Mount ADXL (or Eddy/Beacon); `SHAPER_CALIBRATE` / resonance; save shaper type/freqs; optionally raise accel stepwise.

**📊 Capture**  
- [ ] Shaper X type/freq: `___ / ___ Hz`  
- [ ] Shaper Y type/freq: `___ / ___ Hz`  
- [ ] Recommended max accel: `___`  
- [ ] Ringing coupon before/after (photo or note)  

**✅ Pass**  
3 consecutive cal runs freqs within **±5%**; ringing reduced; enables safer speed climb for G5.

---

## D2 · Homeostasis learning block (environment self-anneal)

| | |
|---|---|
| **⏱ Duration** | **5–10 successful prints** over days (not one sitting)  
| **Each print** | Normal fixture/coupon time |

**🧪 What is done**  
After each success/fail, call `observe_outcome` (or future guardian hook) with quality score + settings used. Memory key = bin × enclosure × SKU.

**📊 Capture (per print)**  
- [ ] Env bin / enclosure  
- [ ] Soak / bed / nozzle / speed factor used  
- [ ] Quality score 0–1  
- [ ] Success Y/N  
- [ ] Homeostasis sample count after: `___`  

**✅ Pass**  
After ≥5 successes, soak/temps stop oscillating wildly; distance_from_homeostasis trends down.

---

## D3 · G7 · Reliability soak

| | |
|---|---|
| **⏱ Duration** | **≥ 2 hours** idle thermal or light duty; ideally **24–48 h** watch for logs  
| **What** | Leave printer on; optional periodic heat cycles; watch MCU loss, log growth, disk |

**📊 Capture**  
- [ ] Soak hours: `___`  
- [ ] MCU losses: `___` (must be 0)  
- [ ] Disk free start/end: `___ / ___`  
- [ ] Log growth MB/day: `___` (fail if > ~50 MB/day spam)  
- [ ] Heartbeat misses: `___`  

**✅ Pass (G7)**  
≥2 h with 0 MCU losses; controlled logs; recovers to ready after power cycle.

---

## D4 · Full calibration campaign `FORGE_CAL_FULL` (Phase 3)

| | |
|---|---|
| **⏱ Duration** | **2–4 hours** first full run (PID + shaper + probe + mesh + flow + PA + coupon + measure)  
| **Arming** | Requires campaign arm token (zero-trust) |

**🧪 Steps (exact order)**  
1. PID (nozzle + both beds) — **15–40 min**  
2. Resonance/shaper — **10–20 min** (if sensor)  
3. Probe Z calibrate — **5–10 min**  
4. Hot mesh after soak — **10–20 min**  
5. Flow single-wall — **15–30 min**  
6. PA pattern — **15–30 min**  
7. Dimensional coupon — **20–45 min**  
8. Caliper import / fit — **5–10 min**  
9. Optional anneal loop — **+2–3 h**  

**📊 Capture**  
Campaign journal events for each step OK/fail; final scale/flow/PA written; evidence blob saved.

**✅ Pass**  
Campaign reaches `done` without hard fail; second coupon improves vs first.

---

# SECTION E — Master schedule (suggested day plans)

## Half-day “smoke + mesh” (no filament) — **~45–90 min**

| Order | Test | ⏱ |
|---|---|---|
| 1 | A0 unit + G0 | 5 min |
| 2 | A3 G1 live | 2 min |
| 3 | B1 dual-bed soak smoke | 10 min |
| 4 | B2 mesh (hot if possible) | 15 min |
| 5 | B3–B4 env + macros | 5 min |

## Full Phase 1 acceptance day (with HTPLA) — **~2–4 hours**

| Order | Test | ⏱ |
|---|---|---|
| 1 | Half-day smoke | 1 h |
| 2 | C1 accuracy bar + T0 | 1 h |
| 3 | Measure + CSV import | 15 min |
| 4 | Decide: G3 pass? | — |

## Precision + speed weekend block — **~4–8 hours**

| Order | Test | ⏱ |
|---|---|---|
| 1 | C2 three reprints G4 | 2–4 h |
| 2 | C4 speed trial G5 | 1 h |
| 3 | Optional C6 anneal start | +3 h |

---

# SECTION F — Quick reference: gate → test map

| Gate | Primary test(s) | ⏱ ballpark | Key metric |
|---|---|---|---|
| G0 | A0 | 5 min | all unit tests pass |
| G1 | A3 | 2 min | printer ready |
| G2 | B1 + B2 + D1 | 20 min–2 h | mesh p2p; shaper stable |
| G3 | C1 | 40–70 min | \|err\| ≤ 0.20 mm / 100 mm |
| G4 | C2 | 1.5–3.5 h | span ≤ 0.10 mm |
| G5 | C3+C4 | +1 print | ≥25% faster than T0 w/ G3 |
| G6 | C6 | 2.5–4 h | post-anneal dims in band |
| G7 | D3 | ≥2 h | 0 MCU loss; log health |

---

# SECTION G — Data we are systematically collecting

| Domain | Variables | Used for |
|---|---|---|
| **Thermal** | dual-bed temps, power, soak time, ambient T | adhesion, warp, soak policy |
| **Geometry map** | mesh min/max/p2p, probe quality | first layer, Z accuracy |
| **Dimensional** | caliper vs nominal, scale, hole Ø | accuracy/precision gates, anneal model |
| **Time** | T0, trial times, role speeds | multi-objective speed pillar |
| **Quality rubric** | first layer, elephant foot, delam, surface | hard fail + J score |
| **Moisture** | RH prior, droop, heater power, risk level | flow/temp/speed derate |
| **Environment bin** | T, RH, enclosure, draft | homeostasis memory key |
| **Motion** | shaper freqs, accel ceilings | safe speed unlock |
| **Reliability** | MCU losses, disk, log growth | G7 / unattended claim |

---

# SECTION H — Operator checklist (print this page)

**Date:** __________ **Filament lot:** __________ **Nozzle:** __________  

- [ ] Heartbeat OK  
- [ ] G0  
- [ ] G1  
- [ ] B1 dual-bed  
- [ ] B2 mesh p2p = ______ mm  
- [ ] C1 bar err = ______ mm · time = ______ min (T0?)  
- [ ] C2 span = ______ mm  
- [ ] C4 improvement = ______ %  
- [ ] Notes: ________________________________________________  

**Sign-off (production claim):** G0–G5 required · G6 if annealed · G7 if unattended  

---

*ForgeOS testing sheet v1 — aligns with `docs/zero_trust_gates.md`, Phase 1 results, and multi-objective plan.*
