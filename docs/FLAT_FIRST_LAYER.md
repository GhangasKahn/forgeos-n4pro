# God-tier flat first layer (side-by-side)

## Rule
**Row step ≈ line width** (`spacing_ratio = 1.0`). Lines sit **side by side**, not stacked.

| Pack | line_w | spacing_ratio | step | flow | Result |
|------|--------|---------------|------|------|--------|
| OLD pile-up (bad) | 0.58 | 0.84 | 0.49 | 1.14 | Heavy overlap / ribs-in-valleys |
| **GOD-TIER FLAT** | **0.44** | **1.00** | **0.44** | **1.00** | Kissing sides, sheet flat |

## Tune
- **Gaps between lines** → `spacing_ratio` 0.97–0.98 **or** flow 1.02–1.04  
- **Still piled / raised ridges** → keep ratio 1.0, lower flow 0.96–0.98, or BABY_UP slightly  
- **Scrape / empty** → BABY_UP / raise Z (do not pile plastic to hide low Z)

## Generate
```bash
python3 scripts/generate_g3_bar_gcode.py -o artifacts/gcodes/forgeos_g3_flat_v6.gcode \
  --line-w 0.44 --spacing-ratio 1.0 --first-flow 1.0 --first-speed 12 --length 100.5
```
