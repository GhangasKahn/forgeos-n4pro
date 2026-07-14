# Machine-flat surfaces — ZERO IRONING

**Requirement:** fingernail rub detects **no ridges / no valleys**.  
**Forbidden crutch:** ironing (second pass). Ironing hides bad volume, costs time, and hurts dimensional accuracy.

**Stack:** Wham Bam PEX · Brozzl plated copper 0.4 · Protopasta HTPLA · Klipper/N4 Pro  
**Code:** `forgeos/flat_surface.py`, `scripts/generate_machine_flat_coupon.py`, G3/FL generators

---

## 1. First principles (causal chain)

```
correct cell volume  →  e_area = spacing × layer_height
constant bead width  →  Pressure Advance + stable Q
no reverse valleys   →  MONOTONIC solid fill
no vibration texture →  input shaper + low solid SCV
correct first squish →  locked Z (shop: −0.480)
high speed           →  Q = w × h × v ≤ Q_hotend (seed 12 mm³/s)
```

### Volume balance (the non-negotiable)

| Symbol | Meaning |
|--------|---------|
| `w` | commanded line width |
| `s` | center-to-center spacing |
| `h` | layer height |
| `f` | flow multiplier |

Deposited area ≈ `w × h × f`  
Cell to fill ≈ `s × h`  

**Flat plane ⇒ `f × w = s`**

Machine-flat default used in ForgeOS:

- `s = w`
- `f = 1.00`
- **No** 0.84-ratio pile-up pack (that *creates* ridges you can feel)

### Why ironing is banned here

| Ironing | Machine-flat |
|---------|----------------|
| Second pass melts texture | First pass deposits correct volume |
| Softens edges / dims | Preserves X accuracy for G3 |
| Slow | Solids run at Klipper-limited speed |
| Hides Z/PA mistakes | Forces Z/PA/volume to be right |

---

## 2. Protocol — calibrate once, then print fast

### Gate F0 — Z (first layer only)
1. Live Z locked (shop **−0.480**).
2. First layer must **wet** PEX continuously — no scrape, no round cords.
3. If nail catches **high** ribs: volume too high or Z slightly high → check F1 before babystep spam.
4. If gaps: do **not** go back to 0.84 overlap; fix Z or use `f=1.02` max.

### Gate F1 — Volume (single layer patch)
1. Print `forgeos_machine_flat_coupon.gcode` (monotonic, `s=w`, `f=1`).
2. Nail test + caliper thickness.
3. Pass: no catch, no light valleys between rows.
4. Fail ridge → `f := 0.98` or verify e-steps/rotation_distance.  
   Fail valley → `f := 1.02` then re-check PA.

### Gate F2 — Pressure Advance (bead width vs speed)
1. Standard Klipper PA tower / pattern at **target solid Q** (not only 20 mm/s).
2. PA must be good at **solid_speed** (pack aims ~80–120 mm/s solids).
3. Store in material / `FORGE_SET_PA`.

### Gate F3 — Monotonic high-speed solid
1. Top solids: **monotonic** only (no zigzag V-grooves).
2. `SET_VELOCITY_LIMIT` solid accel + **SCV 3–5 mm/s**.
3. Q ≤ 0.92 × Q_max.

### Gate F4 — Dimensional (G3) still holds
Machine-flat must not steal accuracy: 100 mm bar \|err\| ≤ 0.20 mm after flat pack.

---

## 3. Machine-flat pack (default numbers)

From `machine_flat_pack()` for 0.4 nozzle, Q_max=12 mm³/s, PA≈0.032:

| Role | w | h | s | f | speed (Q-limited) | accel | SCV |
|------|---|---|---|---|-------------------|-------|-----|
| First layer | 0.44 | 0.28 | 0.44 | 1.00 | ~30 mm/s (adhesion; Q allows higher) | 2500 | 3 |
| Solid | 0.44 | 0.20 | 0.44 | 1.00 | ~120 mm/s class | 5000 | 5 |
| Top solid | 0.44 | 0.20 | 0.44 | 1.00 | ~80 mm/s | 3500 | 3 |

Exact speeds are **Q-clamped** in code — do not request 300 mm/s solids on 0.4 HTPLA.

### Klipper knobs (macros)

```gcode
FORGE_FLAT_SURFACE_MODE ROLE=first   ; or solid / top
FORGE_FLAT_SURFACE_MODE ROLE=solid
FORGE_SET_PA PA=0.032 SMOOTH=0.03
```

Emits `SET_VELOCITY_LIMIT` + PA + fan + M221 for that role.

---

## 4. Path strategy (generator rules)

1. **Monotonic rows** — all extrusions same X direction; travel to next row with wipe/retract, not reverse extrude.
2. **Long strokes** — full panel width; minimize seams.
3. **Perimeter then fill** — 2–3 walls at same `w/s`, then monotonic solid.
4. **No random infill angles on top** — 0° or 90° only for tops.
5. **Same geometry top & first** for `w/s/f`; only speed/fan/accel change.
6. **High speed only after F1/F2 pass.**

---

## 5. Failure tree (no ironing allowed)

| Feel | Likely cause | Fix |
|------|--------------|-----|
| Ridges every row | `s < w` pile or `f>1` | `s=w`, `f=1` |
| Valleys every row | `s > w` or `f<1` or high Z | balance volume; BABY_DOWN 1 click |
| Ridges only at ends | PA too low | raise PA at solid Q |
| Wavy overall | shaper / high SCV | solid SCV 3; check shaper |
| Flat but dim short | shrink / scale | G3 CAD comp, not ironing |
| Flat first, ribbed top | top zigzag | force monotonic top |

---

## 6. Commands

```bash
# Physics + pack report
python3 -c "from forgeos.flat_surface import machine_flat_pack, pack_reports; p=machine_flat_pack(); print(pack_reports(p))"

# Coupon (single-layer + short solid stack)
python3 scripts/generate_machine_flat_coupon.py -o artifacts/gcodes/forgeos_machine_flat_coupon.gcode

# G3 bar using machine-flat pack
python3 scripts/generate_g3_bar_gcode.py -o artifacts/gcodes/forgeos_g3_machine_flat.gcode \
  --machine-flat --length 100.5
```

---

## 7. Promotion rule

Only after **F0–F3** and nail test pass may this pack become default shop first-layer / top solid.  
G3/G4 still gate **accuracy/precision**. Flat is quality — it does not replace G3.
