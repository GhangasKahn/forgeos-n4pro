#!/usr/bin/env python3
"""Test Nothing Phone / Android IP Webcam link.

  python3 scripts/phone_cam_test.py http://192.168.1.42:8080
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forgeos.vision.phone_camera import PhoneCameraSource, grab_phone_frame, score_phone_frame


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.42:8080"
    print("Testing phone camera:", url)
    src = PhoneCameraSource(url, save_dir=str(ROOT / "artifacts" / "phone_cam"))
    info = src.ping()
    print(json.dumps(info, indent=2))
    if not info.get("ok"):
        print(
            "\nSetup:\n"
            "  1) Install **IP Webcam** (Android) on Nothing Phone 4a Pro\n"
            "  2) Same Wi‑Fi as this Mac (not cellular)\n"
            "  3) IP Webcam → scroll down → **Start server**\n"
            "  4) Disable VPN; allow local HTTP if prompted\n"
            "  5) Open the URL shown (http://PHONE_IP:8080) in Mac browser\n"
            "  6) Re-run: python3 scripts/phone_cam_test.py http://PHONE_IP:8080\n"
        )
        return 1
    fr = grab_phone_frame(url)
    out = ROOT / "artifacts" / "phone_cam" / "phone_test.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(fr.jpeg)
    sc = score_phone_frame(url)
    print("saved", out)
    print("score", sc.as_dict())
    print("OK — run vision service:")
    print("  python3 -m forgeos.vision.service --phone-url", url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
