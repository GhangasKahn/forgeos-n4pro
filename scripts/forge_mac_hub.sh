#!/usr/bin/env bash
# Mac-first ForgeOS hub: status / deploy / ssh / open Cursor / gates / sim.
# Canonical daily path — see docs/MAC_EFFICIENT_WORKFLOW.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${FORGE_HOST:-n4pro}"
PRINTER_IP="${FORGE_PRINTER_IP:-192.168.1.178}"
MOONRAKER_URL="${FORGE_MOONRAKER_URL:-http://${PRINTER_IP}:7125}"
MAINSAIL_URL="${FORGE_MAINSAIL_URL:-http://${PRINTER_IP}:81}"

usage() {
  cat <<EOF
ForgeOS Mac hub (LAN primary)

Usage: $0 <command>

  status   Moonraker ping + SSH hostname (light health)
  deploy   rsync to printer via Host n4pro (FORGE_HOST)
  ssh      interactive shell on printer
  open     open this repo in Cursor (local Mac)
  g0       pytest + G0 gate
  zt       zero_trust_live against shop printer
  cal      calibration suite plan full (offline)
  cnc      calibration plan cnc_close (mesh + G3 + G4)
  sim      local CNC digital twin bench (offline)
  mainsail open Mainsail URL
  help     this text

Env overrides: FORGE_HOST FORGE_PRINTER_IP FORGE_MOONRAKER_URL
EOF
}

cmd_status() {
  echo "ForgeOS status"
  echo "  host:      $HOST"
  echo "  mainsail:  $MAINSAIL_URL"
  echo "  moonraker: $MOONRAKER_URL"
  echo

  echo "== Moonraker =="
  if curl -fsS --connect-timeout 3 --max-time 8 \
    "$MOONRAKER_URL/printer/info" | head -c 400; then
    echo
  else
    echo "FAIL: Moonraker unreachable at $MOONRAKER_URL" >&2
    return 1
  fi

  echo
  echo "== SSH ($HOST) =="
  if ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" \
    'hostname; uptime; curl -fsS --max-time 3 localhost:7125/printer/info | head -c 200'; then
    echo
  else
    echo "WARN: BatchMode SSH failed (try: ssh $HOST — password auth / ControlMaster)" >&2
    # Non-batch retry for ControlMaster warm-up with password prompt if needed
    ssh -o ConnectTimeout=8 "$HOST" 'hostname' || {
      echo "FAIL: SSH to $HOST" >&2
      return 1
    }
  fi
  echo
  echo "OK: shop LAN path looks live"
}

cmd_deploy() {
  export FORGE_HOST="$HOST"
  echo "Deploy via FORGE_HOST=$FORGE_HOST"
  exec "$ROOT/scripts/deploy.sh" --apply
}

cmd_ssh() {
  exec ssh "$HOST"
}

cmd_open() {
  if command -v cursor >/dev/null 2>&1; then
    exec cursor "$ROOT"
  elif command -v open >/dev/null 2>&1; then
    # macOS: open with Cursor if registered
    open -a Cursor "$ROOT" 2>/dev/null || open "$ROOT"
  else
    echo "Open this folder in Cursor: $ROOT"
    echo "(cursor CLI not found)"
    return 1
  fi
}

cmd_g0() {
  python3 -m pytest -q
  python3 scripts/run_g0_gate.py
}

cmd_zt() {
  exec python3 scripts/zero_trust_live.py --host "$PRINTER_IP" --ssh-probe
}

cmd_cal() {
  python3 scripts/run_calibration_suite.py list
  echo
  python3 scripts/run_calibration_suite.py plan full
}

cmd_cnc() {
  python3 scripts/run_calibration_suite.py plan cnc_close
  echo
  echo "Next: measure G3 mean → analyze g3 --measured <mm>"
  echo "      then G4 ×3 → analyze g4 --measurements a b c"
}

cmd_sim() {
  exec python3 scripts/local_cnc_bench.py
}

cmd_mainsail() {
  echo "$MAINSAIL_URL"
  if command -v open >/dev/null 2>&1; then
    open "$MAINSAIL_URL" || true
  fi
}

main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    status)   cmd_status "$@" ;;
    deploy)   cmd_deploy "$@" ;;
    ssh)      cmd_ssh "$@" ;;
    open)     cmd_open "$@" ;;
    g0)       cmd_g0 "$@" ;;
    zt)       cmd_zt "$@" ;;
    cal)      cmd_cal "$@" ;;
    cnc)      cmd_cnc "$@" ;;
    sim)      cmd_sim "$@" ;;
    mainsail) cmd_mainsail "$@" ;;
    help|-h|--help) usage ;;
    *)
      echo "Unknown command: $cmd" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
