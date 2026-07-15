# Cloud SSH bridge (fallback only)

**You do not need this for normal work.**

Daily shop path is Mac-on-LAN:

```bash
cd ~/forgeos-n4pro
./scripts/forge_mac_hub.sh open
./scripts/forge_mac_hub.sh deploy
./scripts/forge_mac_hub.sh status
```

See [MAC_EFFICIENT_WORKFLOW.md](MAC_EFFICIENT_WORKFLOW.md).

---

## When this doc applies

Use a cloud → shop tunnel **only** if:

- You are away from the LAN and must run live gates against the real printer, **or**
- A cloud agent must prove real Moonraker/SSH (not the RFC1918 SYN-sink soft-pass)

Otherwise: stay on the Mac hub. Local sim (`./scripts/forge_mac_hub.sh sim`) covers offline logic.

## Why cloud agents fail without a real tunnel

| Path | What happens |
|---|---|
| Direct `192.168.1.178` from cloud | TCP may look “open”; payloads are empty / RST — **not** the printer |
| Soft-connect | Never counts as live G1 |
| Real reverse tunnel / Tailscale / WireGuard | SSH banner + Moonraker JSON = real atoms |

Zero-trust: require an SSH banner or Moonraker JSON before claiming live.

## Minimal reverse tunnel (optional)

On the **Mac** (or a always-on LAN host), expose printer SSH to a jump box the cloud can reach:

```bash
# Example shape only — replace JUMP with your host
ssh -N -R 2222:192.168.1.178:22 jump.example.com
```

Then from the cloud agent:

```bash
export FORGE_HOST=mks@jump.example.com
# or: ssh -p 2222 mks@jump.example.com
python3 scripts/wait_for_printer.py --host jump.example.com --port 2222
python3 scripts/zero_trust_live.py --host <reachable-moonraker-ip>
```

Prefer key auth. Do not commit passwords or private keys.

## Safer alternative: Tailscale / WireGuard

1. Install Tailscale (or WireGuard) on Mac + printer (or on Mac as subnet router for `192.168.1.178/32`).
2. From cloud: use the Tailscale IP / MagicDNS name instead of RFC1918.
3. Keep ControlMaster Host `n4pro` pointed at that reachable name when remote.

## Cloud agent checklist

Before claiming live:

1. `scripts/wait_for_printer.py` reports **real** (SSH banner or Moonraker JSON)
2. `zero_trust_live.py` atoms show non-empty HTTP/SSH payloads
3. Never promote on twin alone (`sim:true` ≠ printer)

## Related

- [MAC_EFFICIENT_WORKFLOW.md](MAC_EFFICIENT_WORKFLOW.md) — canonical daily path  
- [LOCAL_CNC_BENCH.md](LOCAL_CNC_BENCH.md) — offline twin when you do not need the printer  
- [zero_trust_gates.md](zero_trust_gates.md) — G0–G7 bar  
