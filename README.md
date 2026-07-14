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
```

## Deploy to printer (safe default = dry-run)

```bash
./scripts/deploy.sh           # dry-run
./scripts/deploy.sh --apply   # rsync code + copy overlays to config/forgeos
```

Then **manually** include overlays in `printer.cfg` after backup (deploy never auto-rewrites live printer.cfg).

## Zero-trust gates

See [docs/zero_trust_gates.md](docs/zero_trust_gates.md).

Production fixtures require **G0–G5**. Annealed claims add **G6**. Unattended claims add **G7**.

## Multi-objective score

```text
J = 0.30*accuracy + 0.25*precision + 0.25*quality + 0.20*time
```

Hard fails: dim error > 0.20 mm / 100 mm, precision span > 0.10 mm, delam / first-layer fail.  
Fast-and-wrong never promotes.

## Hardware

- Hardened nozzle (CF: ≥0.5 mm)
- ADXL or Beacon/Eddy
- Dryer + calipers + anneal oven

## Status

**Phase 0 complete:** skeleton, materials, safety, journal, optimizers, gates, Klipper overlays, unit tests.  
Next: Phase 1 live dual-bed/print baseline on the printer + journal T0 cycle time.
