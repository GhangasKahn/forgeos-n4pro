# Mac-efficient ForgeOS workflow (canonical)

**Normal work happens on your Mac on the shop LAN.**  
Cloud agents / tunnels are fallback only — see [CLOUD_SSH_BRIDGE.md](CLOUD_SSH_BRIDGE.md).

## Why Mac-first

| Constraint | Reality |
|---|---|
| Printer | `192.168.1.178` (`znp-k1`) — private LAN |
| Cloud agent | Cannot reach real Moonraker/SSH (RFC1918 SYN-sink) |
| Your Mac | Same Wi‑Fi → SSH, Mainsail, rsync, calipers |

Zero-trust: prove live gates from the Mac (or a real tunnel), never from a cloud soft-pass.

## Daily loop

```bash
cd ~/forgeos-n4pro
./scripts/forge_mac_hub.sh open      # Cursor on this Mac
# ... edit / pytest / cal suite ...
./scripts/forge_mac_hub.sh deploy    # rsync → printer via Host n4pro
./scripts/forge_mac_hub.sh status    # light health check
```

| Surface | URL / command |
|---|---|
| Mainsail | http://192.168.1.178:81 |
| Moonraker | http://192.168.1.178:7125 |
| SSH | `ssh n4pro` → `mks@192.168.1.178` (default pw `makerbase` if unchanged) |

## One-time Mac SSH setup (ControlMaster)

Put this in `~/.ssh/config` (Mac):

```sshconfig
Host n4pro
  HostName 192.168.1.178
  User mks
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h:%p
  ControlPersist 10m
  ServerAliveInterval 30
  ServerAliveCountMax 3
```

Then:

```bash
ssh-copy-id n4pro   # optional; else password makerbase
ssh n4pro 'hostname; curl -s localhost:7125/printer/info | head -c 200'
```

`deploy.sh` defaults to `FORGE_HOST=n4pro` so rsync/ssh reuse the multiplexed socket.

## Hub commands

```bash
./scripts/forge_mac_hub.sh status   # ping Moonraker + SSH hostname
./scripts/forge_mac_hub.sh deploy   # ./scripts/deploy.sh --apply
./scripts/forge_mac_hub.sh ssh      # interactive shell on printer
./scripts/forge_mac_hub.sh open     # open this repo in Cursor (local)
./scripts/forge_mac_hub.sh g0       # pytest + G0 gate
./scripts/forge_mac_hub.sh zt       # zero_trust_live against 192.168.1.178
./scripts/forge_mac_hub.sh sim      # local digital twin bench (offline)
```

## Cursor lightness

- `.cursorignore` skips `artifacts/gcodes`, `*.gcode`, `*.stl`, journals
- Prefer editing overlays + `forgeos/` + docs — not dumping mesh JSON into chat
- Optional Cursor / VS Code user settings (Search + watcher):

```json
{
  "search.exclude": {
    "**/artifacts/gcodes/**": true,
    "**/*.gcode": true,
    "**/*.stl": true,
    "**/.venv/**": true
  },
  "files.watcherExclude": {
    "**/artifacts/gcodes/**": true,
    "**/*.gcode": true,
    "**/.venv/**": true,
    "**/__pycache__/**": true
  }
}
```

## Offline vs live

| Mode | When | Command |
|---|---|---|
| **Live shop** | Mac on LAN | `forge_mac_hub.sh zt` / `status` / `deploy` |
| **Local sim** | Plane / no printer | `forge_mac_hub.sh sim` or `zero_trust_live.py --sim` |
| **Cloud bridge** | Rare remote | [CLOUD_SSH_BRIDGE.md](CLOUD_SSH_BRIDGE.md) |

## CNC bar (unchanged)

- G3 ≤ **0.10 mm** / 100 mm  
- G4 span ≤ **0.05 mm** + Cpk ≥ 1.0  
- Mesh p2p ≤ **0.25 mm**
