# ForgeOS N4 Pro

Greenfield **OpenNeptune-class** process OS for the **Elegoo Neptune 4 Pro**, built for **Protopasta HTPLA / HTPLA-CF** fixtures used in woodworking and engineering shop protocols.

**Mandate:** optimize **SPEED × PRECISION × ACCURACY × QUALITY** together.  
**Bar:** zero-trust multi-verification gates (G0–G7) before any “production / public / competitive” claim.

Printer on this network: `mks@192.168.1.178` (`znp-k1`).

## What this is

| Layer | Role |
|---|---|
| Klipper configs | Mechanical truth + dual-bed soak macros + preflight |
| `forgeos/` Python | Materials, safety arming, journal, optimizers, guardian, gates |
| Material packs | Protopasta science as data |
| Gates | GOD-TIER promotion protocol (not vibes) |

**Not** a port of the old OmniForge/`legionforge` tree.

## Quick start (Mac)

```bash
cd ~/forgeos-n4pro
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 scripts/run_g0_gate.py
python3 scripts/calibrate.py audit
python3 scripts/calibrate.py next
```

## Deploy to printer (safe default = dry-run)

```bash
./scripts/deploy.sh           # dry-run
./scripts/deploy.sh --apply   # rsync code + copy overlays to config/forgeos
```

Then **manually** add `[include forgeos/forge_phase1.cfg]` after backing up
OpenNept4une's `printer.cfg` and `SAVE_CONFIG` section. Deploy never rewrites
the live root config.

## Zero-trust gates

See [docs/zero_trust_gates.md](docs/zero_trust_gates.md).

Production fixtures require **G0–G5**. Annealed claims add **G6**. Unattended claims add **G7**.

## Multi-objective score

```text
J = 0.30*accuracy + 0.25*precision + 0.25*quality + 0.20*time
```

Hard fails: dim error > 0.20 mm / 100 mm, precision span > 0.10 mm, delam / first-layer fail.  
Fast-and-wrong never promotes.

## Hardware for the full quality envelope

- Hardened nozzle for abrasive CF only (CF: ≥0.5 mm)
- Rigid accelerometer mount for input-shaper measurement
- Dryer + calipers + anneal oven

## Shop stack (your hardware)

Optimized for:

- **Wham Bam PEX** flex sheet  
- **[Brozzl Plated Copper 0.4 mm](https://www.brozzl.com/products/plated-copper-nozzles/)** (high conductivity; soft — not for CF)  
- **Protopasta HTPLA** (primary filament)

```bash
python3 scripts/print_stack_profile.py
python3 scripts/generate_g3_bar_gcode.py --use-stack --mode ztune -o artifacts/gcodes/forgeos_z_tune_square.gcode
```

See [docs/STACK_PEX_BROZZL_PROTOPASTA.md](docs/STACK_PEX_BROZZL_PROTOPASTA.md).

## Moisture (no dryer sensor)

Soft-sensor from hotend **temp droop + heater power** under extrusion → risk score → safe flow/temp/speed response.  
Not absolute water %. See [docs/moisture_soft_sensor.md](docs/moisture_soft_sensor.md).

## Environment / basement homeostasis

Optimizes **before / during / after** for cold, humid basements, open vs enclosed, drafts, and other shop climates.  
Self-anneals parameters toward a stable attractor per environment bin.

```bash
python3 scripts/env_plan.py --profile environments/basement_default.yaml
```

See [docs/environment_homeostasis.md](docs/environment_homeostasis.md).

## Zero-vision adaptive control (primary — no cameras)

Closed-loop **dual-bed + nozzle + flat + PA/flow/speed** from Moonraker only.  
Push N4 Pro toward 10k-class process control **before** buying vision.

```bash
# Safe real-time brain (suggest-only)
python3 -m forgeos.adaptive.service --interval 0.5 -v
# After validation:
python3 -m forgeos.adaptive.service --interval 0.5 --arm
```

→ [docs/ZERO_VISION_10K.md](docs/ZERO_VISION_10K.md) · [docs/MACHINE_FLAT_ZERO_IRON.md](docs/MACHINE_FLAT_ZERO_IRON.md)

## Vision + Jetson ML (optional later)

Multi-view RGB + IR on **NVIDIA Jetson** *adds* observations; does not replace zero-vision brain.

- Architecture: [docs/VISION_ML_JETSON_STACK.md](docs/VISION_ML_JETSON_STACK.md)
- Real-time vision loop: `python3 -m forgeos.vision.service --interval 0.25`
- BOM: [docs/BOM_GOD_TIER_VISION_RIG.md](docs/BOM_GOD_TIER_VISION_RIG.md)

**Restore shop process state after reboot:**
```bash
python3 scripts/restore_saved_state.py
# state file: configs/saved_state_shop_n4pro.yaml  (Z=-0.480, PEX, Brozzl, HTPLA, 65/214)
```

## Testing sheet

Operator runbook with **duration**, **exact procedure**, and **metrics to capture** per test/gate:

→ [docs/TESTING_SHEET.md](docs/TESTING_SHEET.md)

## Dependency-ordered calibration

The canonical machine envelope is `configs/neptune4pro.yaml`. Measured PID,
probe, mesh and shaper values remain per-printer values in Klipper
`SAVE_CONFIG`; they are never guessed from the repository.

```bash
python3 scripts/calibrate.py plan
python3 scripts/calibrate.py init
python3 scripts/calibrate.py next
```

The suite covers electrical/mechanical inspection, dual-zone PID, probe
repeatability/Z, bed mesh, bed-slinger resonance, extrusion, every major
material tuning control, dimensional compensation, acceleration and 3×
repeatability. See [the calibration protocol](docs/calibration_protocol.md).

## Status

**Software baseline:** machine profile, materials, safety, journal, optimizers,
gates, Klipper overlays and calibration recorder are testable offline.
Physical quality claims remain provisional until the suite's printer-side
evidence and three-print repeatability gate pass.
