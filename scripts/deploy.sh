#!/usr/bin/env bash
# Non-destructive deploy of ForgeOS artifacts to Neptune 4 Pro.
# Default: DRY RUN. Pass --apply to execute.
set -euo pipefail

HOST="${FORGE_HOST:-mks@192.168.1.178}"
REMOTE_ROOT="${FORGE_REMOTE_ROOT:-/home/mks/forgeos-n4pro}"
REMOTE_CFG="${FORGE_REMOTE_CFG:-/home/mks/printer_data/config/forgeos}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

echo "ForgeOS deploy"
echo "  local:  $ROOT"
echo "  host:   $HOST"
echo "  code:   $REMOTE_ROOT"
echo "  cfg:    $REMOTE_CFG"
echo "  mode:   $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"

RSYNC_OPTS=(-avz --delete)
RSYNC_OPTS+=(--exclude '.git' --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'artifacts/*.sqlite3')

if [[ $APPLY -eq 0 ]]; then
  RSYNC_OPTS+=(--dry-run)
fi

echo "== sync repo =="
rsync "${RSYNC_OPTS[@]}" "$ROOT/" "$HOST:$REMOTE_ROOT/"

echo "== sync klipper overlays into printer_data/config/forgeos =="
if [[ $APPLY -eq 1 ]]; then
  ssh "$HOST" "mkdir -p '$REMOTE_CFG' && cp -a '$REMOTE_ROOT/klipper/base/printer_n4pro.cfg' '$REMOTE_CFG/' && cp -a '$REMOTE_ROOT/klipper/overlays/'*.cfg '$REMOTE_CFG/' && ls -la '$REMOTE_CFG'"
  echo "NOTE: printer.cfg is NOT auto-rewritten. Manually include forgeos/*.cfg after backup."
else
  echo "(dry-run) would copy klipper base+overlays to $REMOTE_CFG"
fi

echo "Done."
