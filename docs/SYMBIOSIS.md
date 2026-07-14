# Grok ↔ Agent swarm symbiosis

Grok and the film agents work through shared files + a bridge process.

```
  Grok (this chat / tools)
       │  grok_emit() / GROK_OUTBOX.jsonl
       ▼
  symbiosis_bridge.py  ←→  FilmSwarm bus (director, capture, optics, …)
       │  GROK_INBOX.jsonl + SYMBIOSIS.json
       ▼
  Grok reads status / inbox / latest.jpg
```

## Paths

| File | Who writes | Purpose |
|------|------------|---------|
| `artifacts/film_swarm/GROK_OUTBOX.jsonl` | Grok | Commands |
| `artifacts/film_swarm/GROK_INBOX.jsonl` | Agents | Events for Grok |
| `artifacts/film_swarm/SYMBIOSIS.json` | Bridge | Live snapshot |
| `artifacts/film_swarm/COMMANDS.json` | Grok | Last command |
| `artifacts/film_swarm/latest.jpg` | Capture | Shared eyes |

## Commands

```bash
python3 scripts/grok_swarm_cmd.py burst --count 12
python3 scripts/grok_swarm_cmd.py closeup
python3 scripts/grok_swarm_cmd.py focus
python3 scripts/grok_swarm_cmd.py torch --on
python3 scripts/grok_swarm_cmd.py scene --scene closeup
python3 scripts/grok_swarm_cmd.py test --suite full
python3 scripts/grok_swarm_cmd.py status
python3 scripts/grok_swarm_cmd.py inbox
```

## Bridge

```bash
python3 scripts/symbiosis_bridge.py --phone-url http://192.168.1.250:8080 \
  --adb-serial 192.168.1.250:35853 -v --bootstrap-test
```

## Phone HUD

`http://192.168.1.140:8787/agents` — agents IRT  
`http://127.0.0.1:8787/` — full film HUD
