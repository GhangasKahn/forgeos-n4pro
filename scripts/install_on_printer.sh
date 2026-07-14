#!/usr/bin/env bash
# Run ON the printer after rsync. Installs Python deps for mks user.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 -m pip install --user -r "$ROOT/requirements.txt"
echo "ForgeOS Python deps installed for $(whoami)"
echo "Next: wire klipper includes from $ROOT/klipper into printer_data/config (with backup)."
