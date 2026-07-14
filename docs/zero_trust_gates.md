# Zero-Trust Multi-Verification Gates (GOD-TIER bar)

ForgeOS does **not** claim RatRig / Bambu / LulzBot competitive status until gates pass.

## Principle

1. **Zero trust of claims** — code comments, marketing, or a single good print prove nothing.
2. **Multi-verification** — each pillar (speed, precision, accuracy, quality, reliability) has independent evidence.
3. **Hard fail** — a fast wrong part is FAIL; a pretty slow part is FAIL for production packs that claim speed.
4. **Promotion only** — recipes enter production via journaled promotion after gates.

## Gate ladder

| Gate | Name | Evidence |
|---|---|---|
| G0 | Static / unit | `pytest` green; material packs validate |
| G1 | Hardware preflight | MCU ready; disk free; hardened nozzle if abrasive |
| G2 | Process sensors | Mesh peak-to-peak; shaper present; thermal stable |
| G3 | Accuracy | 100 mm coupon \|error\| ≤ 0.20 mm (aim 0.15) |
| G4 | Precision | 3 reprints span ≤ 0.10 mm |
| G5 | Speed | ≥25% faster than baseline **while G3/G4/quality hold** |
| G6 | Anneal (optional claim) | Post-anneal dims within band with compensation |
| G7 | Reliability (unattended claim) | ≥2h soak, 0 MCU losses, log growth capped |

## Production release matrix

| Claim | Required gates |
|---|---|
| Internal dev only | G0 |
| Shop pilot (attended) | G0–G4 |
| Production fixtures | G0–G5 |
| Annealed HTPLA fixtures | G0–G6 |
| Unattended overnight | G0–G5 + G7 |

## Competitive posture (honest)

Competing with Bambu/RatRig/LulzBot means **process capability + reliability + cycle time**, not copying closed ecosystems.

ForgeOS wins for **your** shop if:

- HTPLA/HTPLA-CF fixtures hit dimensional band with known anneal model
- Role-based speed beats stock Elegoo cycle time without reprint loops
- Zero-trust gates prevent “feels good” configs from becoming default

## Running gate checks (software)

```bash
cd forgeos-n4pro
python3 -m pytest -q
python3 scripts/run_g0_gate.py
```
