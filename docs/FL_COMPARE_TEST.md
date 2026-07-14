# First-layer compare test (PA-style)

File: `forgeos_fl_compare_v1.gcode`

Single-layer multi-panel coupon so you can **see** best first-layer geometry.

## Layout (bed, looking from front)

**Columns L→R = spacing_ratio** (row step / line width)

| Col 0 | Col 1 | Col 2 | Col 3 |
|-------|-------|-------|-------|
| 0.92  | 0.96  | **1.00** | 1.04 |
| more pile | slight pile | side-by-side | slight gap risk |

**Rows B→T = first_flow**

| Row 0 | Row 1 | Row 2 |
|-------|-------|-------|
| 0.96  | **1.00** | 1.04 |

Fixed: line width **0.44 mm**, height **0.28 mm**, **12 mm/s**, Z=**−0.480**, PA **0.032**.

Legend stripes under the grid: spacing only @ flow 1.00.

## How to pick winner
1. Want **flat sheet**, beads **kissing**, no raised ridges, no valleys/gaps.
2. Note winning **spacing_ratio + flow**.
3. Tell agent: e.g. `winner spacing=1.00 flow=1.00` → locks into G3 flat generator defaults.
4. Optional fine: if almost perfect but tiny gaps → 0.98; if tiny ridges → 1.00 + flow 0.98.

## Generate
```bash
python3 scripts/generate_fl_compare_gcode.py -o artifacts/gcodes/forgeos_fl_compare_v1.gcode
```
