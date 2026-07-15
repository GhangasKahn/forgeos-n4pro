# ForgeOS N4 Pro

Greenfield **OpenNeptune-class** process OS for the **Elegoo Neptune 4 Pro**, built for **Protopasta HTPLA / HTPLA-CF** fixtures used in woodworking and engineering shop protocols.

**Mandate:** optimize **SPEED × PRECISION × ACCURACY × QUALITY** together.  
**Bar:** CNC-tier zero-trust gates (G0–G7) — default **|err| ≤ 0.10 mm / 100 mm**, **span ≤ 0.05 mm**, **Cpk ≥ 1.0**.

Printer on this network: `mks@192.168.1.178` (`znp-k1`).

## Daily path (Mac on LAN)

**Normal work is Mac-first.** Cloud tunnels are fallback only.

```bash
cd ~/forgeos-n4pro
./scripts/forge_mac_hub.sh open      # Cursor on this Mac
# ... edit ...
./scripts/forge_mac_hub.sh deploy    # rsync via Host n4pro (ControlMaster)
./scripts/forge_mac_hub.sh status    # light health check
```

Mainsail: http://192.168.1.178:81  

→ [docs/MAC_EFFICIENT_WORKFLOW.md](docs/MAC_EFFICIENT_WORKFLOW.md) · fallback only: [docs/CLOUD_SSH_BRIDGE.md](docs/CLOUD_SSH_BRIDGE.md)

## What this is

| Layer | Role |
|---|---|
| Klipper configs | Mechanical truth + dual-bed soak + calibration macros |
| `forgeos/` Python | Materials, safety, journal, CNC precision, optimizers, gates |
| Material packs | Protopasta science as data |
| Gates | CNC / GOD-TIER promotion protocol |

**Not** a port of the old OmniForge/`legionforge` tree. Phone/film swarm experiments removed — focus is process control + calipers.

## Quick start

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 scripts/run_g0_gate.py
python3 scripts/run_calibration_suite.py plan full
```

## Deploy to printer (safe default = dry-run)

Defaults to SSH Host `n4pro` (multiplexed). Override with `FORGE_HOST=mks@192.168.1.178` if needed.

```bash
./scripts/forge_mac_hub.sh deploy   # apply (preferred)
./scripts/deploy.sh                 # dry-run
./scripts/deploy.sh --apply         # rsync + copy overlays to config/forgeos
```

Then **manually** include overlays in `printer.cfg` after backup (deploy never auto-rewrites live printer.cfg).

## Zero-trust / CNC gates

See [docs/zero_trust_gates.md](docs/zero_trust_gates.md).

| Tier | Accuracy (G3) | Precision (G4) |
|---|---|---|
| CNC (default) | ≤ 0.10 mm | ≤ 0.05 mm + Cpk ≥ 1.0 |
| Fixture | ≤ 0.15 mm | ≤ 0.08 mm |
| Shop | ≤ 0.20 mm | ≤ 0.10 mm |

## Multi-objective score

```text
J = 0.35*accuracy + 0.30*precision + 0.20*quality + 0.15*time
```

Hard fails: dim error > 0.10 mm / 100 mm, precision span > 0.05 mm, delam / first-layer fail.  
Fast-and-wrong never promotes.

## Hardware

- Hardened nozzle (CF: ≥0.5 mm)
- ADXL or Beacon/Eddy
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

## Vision (optional later)

Telemetry-only loop available; Jetson cameras are optional and do **not** replace zero-vision + calipers.

```bash
python3 -m forgeos.vision.service --interval 0.25
```

See [docs/VISION_ML_JETSON_STACK.md](docs/VISION_ML_JETSON_STACK.md).

**Restore shop process state after reboot:**
```bash
python3 scripts/restore_saved_state.py
# state file: configs/saved_state_shop_n4pro.yaml  (Z=-0.480, PEX, Brozzl, HTPLA, 65/214)
```

## Testing sheet

Operator runbook with **duration**, **exact procedure**, and **metrics to capture** per test/gate:

→ [docs/TESTING_SHEET.md](docs/TESTING_SHEET.md)

## Calibration suite (one-time + fine-tune)

Full catalog, analysis, G-code generation, and live orchestration:

```bash
python3 scripts/run_calibration_suite.py list
python3 scripts/run_calibration_suite.py plan full
python3 scripts/run_calibration_suite.py analyze g3 --measured 99.92
python3 scripts/run_calibration_suite.py gcode flow_cube -o artifacts/gcodes/flow_cube.gcode
```

→ [docs/CALIBRATION_SUITE.md](docs/CALIBRATION_SUITE.md)

## Computer use / browser senses

Open-source [browser-use](https://github.com/browser-use/browser-use) + Playwright + XFCE desktop control (`DISPLAY=:1`):

```bash
python3 scripts/computer_use.py senses
browser-harness --doctor
```

→ [docs/COMPUTER_USE.md](docs/COMPUTER_USE.md)

## Local CNC bench (digital twin)

When the shop printer is unreachable, prove process logic offline on a **labeled** Moonraker twin (`sim:true`):

```bash
python3 scripts/local_cnc_bench.py
# equivalent:
python3 scripts/zero_trust_live.py --sim
```

→ [docs/LOCAL_CNC_BENCH.md](docs/LOCAL_CNC_BENCH.md)

## Status

**CNC-tier process OS:** calibration suite, zero-vision adaptive, CNC gates (0.10 / 0.05 / Cpk), film/phone swarm removed.  
**Mac hub:** `forge_mac_hub.sh` + Host `n4pro` ControlMaster — primary live path.  
**Local bench:** twin G1/mesh + G-code physics + CNC metrology discrimination — ALL_PASS.  
Next: Mac LAN → real G3 mean calipers (cloud tunnel only if away).
