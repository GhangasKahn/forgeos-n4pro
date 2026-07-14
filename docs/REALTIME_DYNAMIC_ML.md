# Real-time dynamic ML / vision control

**Requirement:** all process + ML updates are **fully dynamic in real time** — not batch, not post-print only.

## Architecture

```
Moonraker telemetry ──┐
Cameras (optional)  ──┼─→ features → DynamicController → actions
Thermal (optional)  ──┘         │
                                ├─ AdaptiveState (EMA, every tick)
                                ├─ JSONL journal (online learning later)
                                └─ hot-reload vision_rig.yaml
```

| Module | Role |
|--------|------|
| `forgeos/vision/telemetry_features.py` | Live printer features (Z, temps, progress, volume residual) |
| `forgeos/vision/adaptive_state.py` | Online EMA state + envelopes |
| `forgeos/vision/dynamic_controller.py` | Multi-objective policy → gcode |
| `forgeos/vision/realtime_loop.py` | 4–10 Hz loop, hot-reload, journal |
| `forgeos/vision/service.py` | Process entry (`python3 -m forgeos.vision.service`) |
| `forgeos/flat_surface.py` | Zero-ironing volume model used live |

## Tick rate

Default **0.25 s (4 Hz)**. Config:

```yaml
# configs/vision_rig.yaml
realtime:
  interval_s: 0.25
  alpha: 0.30
  min_apply_interval_s: 1.5
  zero_ironing: true
```

Change YAML while service runs → **hot-reloaded** next tick.

## Modes

| Mode | Behavior |
|------|----------|
| **suggest** (default) | Full dynamic scoring + planned actions; **no** gcode apply |
| **armed** (`--arm` or `policy.auto_apply: true`) | Applies 1 rate-limited action/tick within envelopes |
| **hold** | State updates; actuators frozen |

## Live actuators (dynamic)

- `FORGE_FLAT_SURFACE_MODE ROLE=first|solid|top`
- `FORGE_BABY_UP` / `FORGE_BABY_DOWN`
- `M221` flow nudges (volume balance — **not** ironing)
- `M220` speed for thermal lag / recover

## Run

```bash
# Suggest-only real-time (safe)
python3 -m forgeos.vision.service --interval 0.25

# Armed (shop validated only)
python3 -m forgeos.vision.service --interval 0.25 --arm

# One tick smoke
python3 -m forgeos.vision.service --once -v
```

Journal: `artifacts/vision_rt_journal.jsonl`  
State: `artifacts/vision_adaptive_state.json`

## Cameras

When capture is wired, set `vision_feature_fn` in the loop (or extend service) to return `FirstLayerResult` from frames. Telemetry path stays live even with **zero cameras** so control is always dynamic.

## Zero ironing

Controller never emits ironing. Ribs → small **flow** or **Z** within envelopes; spacing doctrine stays machine-flat (`s=w`).
