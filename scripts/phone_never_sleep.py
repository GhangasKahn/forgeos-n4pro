#!/usr/bin/env python3
"""Force phone screen never off / never sleep via ADB.

  python3 scripts/phone_never_sleep.py
  python3 scripts/phone_never_sleep.py --serial 192.168.1.250:35853
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.vision.adb_phone import AdbPhone, find_adb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=None)
    args = ap.parse_args()
    print("adb:", find_adb())
    serial = args.serial
    if not serial:
        p = ROOT / "artifacts" / "film_cam" / "adb_serial.txt"
        if p.exists():
            serial = p.read_text(encoding="utf-8").strip()
    phone = AdbPhone(serial=serial)
    if not phone.is_connected():
        devs = phone.devices()
        if devs:
            phone.serial = devs[0]
        else:
            print("No ADB device. Connect wireless debugging first.")
            return 1
    print("device:", phone.serial, phone.status_dict())
    res = phone.never_sleep()
    print(json.dumps(res, indent=2))
    # re-assert forever loop note
    print("Screen timeout set to max; stay_on while plugged; deviceidle disabled.")
    print("Keep Wireless debugging ON and preferably charging (battery was low).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
