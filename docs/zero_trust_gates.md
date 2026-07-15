# Zero-Trust Multi-Verification Gates — CNC / GOD-TIER bar

ForgeOS does **not** claim fixture/CNC readiness until gates pass.

## Precision tiers

| Tier | G3 \|err\| / 100 mm | G4 span (3×) | Mesh p2p |
|---|---|---|---|
| shop (legacy) | ≤ 0.20 mm | ≤ 0.10 mm | ≤ 0.80 mm |
| fixture | ≤ 0.15 mm | ≤ 0.08 mm | ≤ 0.40 mm |
| **cnc (default)** | **≤ 0.10 mm** | **≤ 0.05 mm** + **Cpk ≥ 1.0** | **≤ 0.25 mm** |

## Gate ladder

| Gate | Name | CNC evidence |
|---|---|---|
| G0 | Static / unit | `pytest` green; material packs validate |
| G1 | Hardware preflight | MCU ready; disk free; hardened nozzle if abrasive |
| G2 | Process sensors | Mesh p2p ≤ 0.25 mm; shaper present; thermal stable |
| G3 | Accuracy | 100 mm coupon \|error\| ≤ 0.10 mm |
| G4 | Precision | 3 reprints span ≤ 0.05 mm and Cpk ≥ 1.0 |
| G5 | Speed | ≥25% faster than T0 **while G3/G4 hold** |
| G6 | Anneal (optional) | Post-anneal dims within CNC band |
| G7 | Reliability | ≥2h soak, 0 MCU losses, log growth capped |

## Production release matrix

| Claim | Required gates |
|---|---|
| Internal dev only | G0 |
| Shop pilot (attended) | G0–G4 (cnc tier) |
| Production fixtures | G0–G5 |
| Annealed HTPLA fixtures | G0–G6 |
| Unattended overnight | G0–G5 + G7 |

## Running

```bash
python3 -m pytest -q
python3 scripts/run_g0_gate.py
python3 scripts/run_calibration_suite.py analyze g3 --measured 99.95
python3 scripts/run_calibration_suite.py analyze g4 --measurements 100.0 100.02 99.99
```

See [CALIBRATION_SUITE.md](CALIBRATION_SUITE.md) and `forgeos/precision.py`.
