# Multi-agent film capture swarm

Serious multi-agent system for **capturing film/footage** of the printer. Agents **talk on a shared bus** (pub/sub + durable JSONL).

## Agents

| Agent | Role |
|-------|------|
| **director** | Plans shots, modes, close-up sessions, operator prompts |
| **capture** | Full-time `/shot.jpg` grab, bursts, latest frame |
| **optics** | Focus / torch / quality / film presets |
| **adb** | Device wake, launch IP Webcam, screencap (when paired) |
| **printer** | Moonraker telemetry → start/complete/milestone cues |
| **archive** | Session folders + manifest + cue log |
| **comms** | Aggregates bus → `swarm_state.json` for HUD |

## Message topics (examples)

```
film.burst              → capture fires N frames
film.scene              → optics switches preset
film.frame              → new frame metadata
film.printer.event      → print state changes
film.director.cue       → high-level production cues
film.operator.prompt    → human instructions
film.adb                → {op: launch_cam|screencap|wake}
swarm.command           → {cmd: closeup|burst, ...}
```

## Run

```bash
# Stop lone ipcam_agent if you want swarm to own the camera exclusively
python3 -m forgeos.swarm --phone-url http://192.168.1.250:8080 -v

# force opening burst / closeup mode
python3 -m forgeos.swarm --phone-url http://192.168.1.250:8080 --burst 15 --closeup
```

With ADB paired:

```bash
python3 -m forgeos.swarm --phone-url http://192.168.1.250:8080 \
  --adb-serial 192.168.1.250:YYYYY -v
```

## Outputs

```
artifacts/film_swarm/
  LIVE / SWARM_LIVE
  latest.jpg
  bus.jsonl              # all agent chatter
  swarm_state.json       # HUD snapshot
  frames/latest.jpg
  sessions/session_*/    # archived bursts + CUES.txt + manifest
  OPERATOR_PROMPT.txt
```

## HUD

```bash
python3 -m forgeos.vision.hud_server --port 8787
open http://127.0.0.1:8787/
```

Point HUD at `artifacts/film_swarm/latest.jpg` (mirrored by capture agent).

## Production flow (auto documentary)

1. Print starts → **printer** emits event → **director** sets bed scene + burst  
2. 25/50/75/95% milestones → short bursts  
3. Print complete → **closeup session** + operator prompt + long burst  
4. **archive** stores tagged frames into session folder  

## Design rules

- Capture agent owns HTTP camera (avoid multi-client flapping)  
- Optics never iron; only exposure/focus/torch  
- Director is the only mode brain; others execute  
- Bus log is the source of truth for post-production timelines  
