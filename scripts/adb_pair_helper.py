#!/usr/bin/env python3
"""Interactive ADB wireless pair helper for Nothing Phone.

  python3 scripts/adb_pair_helper.py
  python3 scripts/adb_pair_helper.py --pair 192.168.1.250:37123 --code 123456
  python3 scripts/adb_pair_helper.py --connect 192.168.1.250:40555
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.vision.adb_phone import AdbPhone, find_adb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", help="IP:PAIR_PORT from Wireless debugging pair sheet")
    ap.add_argument("--code", help="6-digit pairing code")
    ap.add_argument("--connect", help="IP:CONNECT_PORT from Wireless debugging main page")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    print("adb binary:", find_adb())
    phone = AdbPhone()

    if args.pair and args.code:
        ok, msg = phone.pair(args.pair, args.code)
        print("pair:", ok, msg)
        if not ok:
            return 1
    elif args.pair and not args.code:
        print("Need --code with --pair")
        return 2

    if args.connect:
        ok, msg = phone.connect(args.connect)
        print("connect:", ok, msg)

    print("devices:", phone.devices())
    print("status:", phone.status_dict())
    if phone.is_connected():
        print("optimize:", phone.optimize_for_film())
        print("FULL ADB CONTROL READY")
        return 0

    print(
        """
NOT CONNECTED YET — on the phone:
  1) Developer options → Wireless debugging → ON
  2) Pair device with pairing code
  3) Run:
       python3 scripts/adb_pair_helper.py --pair 192.168.1.250:XXXXX --code NNNNNN
       python3 scripts/adb_pair_helper.py --connect 192.168.1.250:YYYYY
"""
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
