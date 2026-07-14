#!/usr/bin/env python3
"""Control IP Webcam on the phone (camera features).

  python3 scripts/phone_control.py http://192.168.1.250:8080 status
  python3 scripts/phone_control.py http://192.168.1.250:8080 optimize
  python3 scripts/phone_control.py http://192.168.1.250:8080 torch on
  python3 scripts/phone_control.py http://192.168.1.250:8080 focus
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.vision.phone_control import PhoneControl


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    url, cmd = sys.argv[1], sys.argv[2].lower()
    arg = sys.argv[3].lower() if len(sys.argv) > 3 else ""
    pc = PhoneControl(url)

    if cmd == "status":
        print(json.dumps(pc.status(), indent=2)[:2000])
        return 0
    if cmd == "optimize":
        print(json.dumps(pc.optimize_for_bed(), indent=2))
        return 0
    if cmd == "torch":
        print("torch", pc.torch(arg != "off"))
        return 0
    if cmd == "focus":
        print("focus", pc.focus(True))
        return 0
    if cmd == "quality":
        print("quality", pc.quality(int(arg or "70")))
        return 0
    if cmd == "front":
        print("front", pc.front_camera(arg == "on"))
        return 0
    print("unknown command", cmd)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
