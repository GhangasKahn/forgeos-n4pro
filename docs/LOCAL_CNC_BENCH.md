# Local CNC engineering bench (digital twin)

When the shop printer is unreachable, ForgeOS runs a **labeled simulator** so process
logic is proven offline. The twin always sets `sim: true`. Claiming a twin response
as a live printer is a hard fail.

## Run

```bash
python3 scripts/local_cnc_bench.py
# or
python3 scripts/zero_trust_live.py --sim
```

## Layers (all must pass)

| Layer | Atom | Pass rule |
|---|---|---|
| L0 | G0 pytest + materials | zero failures |
| L1 | Twin Moonraker G1 | `state=ready` **and** `sim=true` |
| L2 | Dual-bed heat + mesh | bed≥60 °C, mesh p2p ≤ 0.25 mm CNC; shaper marked DEFERRED |
| L3 | Generate flow/FL/G3 gcode | physics validator 0 fails |
| L4 | CNC metrology discrimination | good set PASSes; bad historical-like set FAILs |

## First-principles G-code physics

```python
from forgeos.gcode_physics import validate_gcode_file
print(validate_gcode_file("artifacts/gcodes/sim_g3_bar.gcode").as_dict())
```

Checks: bed envelope, Z≥0.05 on extrude, finite coords, nozzle/bed temp envelopes, extrusion present.

## Twin API

```bash
python3 -c "from forgeos.sim import serve_background, reset_state; reset_state(); serve_background('127.0.0.1',17125)"
curl -s http://127.0.0.1:17125/printer/info
```

## Zero-lie boundary

- Twin ≠ printer. Shop G1+ requires real Moonraker bytes (SSH banner / JSON) via LAN or tunnel.
- ADXL/shaper is never soft-passed; SIM records `DEFERRED_NO_ADXL_SIM`.
