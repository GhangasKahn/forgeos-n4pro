"""Full ADB control helpers for Android phone (Nothing Phone / etc.).

Requires one-time Wireless debugging pairing:
  Settings → System → Developer options → Wireless debugging
  → Pair device with pairing code → run:
     adb pair PHONE_IP:PAIR_PORT
     adb connect PHONE_IP:CONNECT_PORT

Once authorized, this module can launch apps, keep screen on, keyevents,
screencap, shell settings, force IP Webcam, etc.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

log = logging.getLogger("forgeos.adb")

# Common ADB locations
_ADB_CANDIDATES = [
    "adb",
    str(Path.home() / ".local/bin/adb"),
    str(Path.home() / ".local/platform-tools/adb"),
    "/usr/local/bin/adb",
    "/opt/homebrew/bin/adb",
]


def find_adb() -> str:
    for c in _ADB_CANDIDATES:
        if c == "adb":
            p = shutil.which("adb")
            if p:
                return p
        elif Path(c).is_file():
            return c
    raise FileNotFoundError(
        "adb not found — install platform-tools to ~/.local/platform-tools"
    )


@dataclass
class AdbPhone:
    serial: Optional[str] = None  # e.g. 192.168.1.250:40555
    adb_path: Optional[str] = None

    def __post_init__(self) -> None:
        self.adb_path = self.adb_path or find_adb()

    def _base(self) -> List[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def run(self, *args: str, timeout: float = 20.0) -> Tuple[int, str, str]:
        cmd = self._base() + list(args)
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"
        except Exception as exc:  # noqa: BLE001
            return 1, "", str(exc)

    def devices(self) -> List[str]:
        code, out, err = self.run("devices", timeout=10)
        lines = []
        for line in (out or "").splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                lines.append(parts[0])
        return lines

    def is_connected(self) -> bool:
        devs = self.devices()
        if self.serial:
            return self.serial in devs
        return len(devs) > 0

    def connect(self, hostport: str) -> Tuple[bool, str]:
        code, out, err = self.run("connect", hostport, timeout=15)
        msg = (out + " " + err).strip()
        ok = code == 0 and "connected" in msg.lower()
        if ok:
            self.serial = hostport
        return ok, msg

    def pair(self, hostport: str, code: str) -> Tuple[bool, str]:
        # adb pair ip:port  (code via stdin on newer adb)
        cmd = [self.adb_path, "pair", hostport, code]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            msg = (p.stdout + p.stderr).strip()
            return p.returncode == 0 and "successfully" in msg.lower(), msg
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    # ---- high-level phone ops ----

    def shell(self, *args: str, timeout: float = 15.0) -> Tuple[int, str, str]:
        return self.run("shell", *args, timeout=timeout)

    def keep_awake(self, on: bool = True) -> bool:
        # stay on while plugged/wireless debug; also svc power
        mode = "true" if on else "false"
        c1, _, _ = self.shell("settings", "put", "global", "stay_on_while_plugged_in", "7" if on else "0")
        c2, _, _ = self.shell("svc", "power", "stayon", "true" if on else "false")
        return c1 == 0 or c2 == 0

    def screen_on(self) -> bool:
        code, out, _ = self.shell("dumpsys", "power")
        # wake
        self.shell("input", "keyevent", "KEYCODE_WAKEUP")
        self.shell("wm", "dismiss-keyguard")
        return True

    def brightness(self, value: int = 200) -> bool:
        value = max(1, min(255, int(value)))
        c, _, _ = self.shell("settings", "put", "system", "screen_brightness", str(value))
        return c == 0

    def launch_ip_webcam(self) -> bool:
        # try common IP Webcam package
        packages = [
            "com.pas.webcam/.Rolling",
            "com.pas.webcam/.Main",
            "com.pas.webcam",
        ]
        for p in packages:
            if "/" in p:
                c, o, e = self.shell(
                    "am", "start", "-n", p, timeout=10
                )
            else:
                c, o, e = self.shell(
                    "monkey",
                    "-p",
                    p,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                    timeout=10,
                )
            if c == 0:
                log.info("launched %s", p)
                return True
        # generic intent
        c, o, e = self.shell(
            "am",
            "start",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-p",
            "com.pas.webcam",
            timeout=10,
        )
        return c == 0

    def force_stop(self, package: str) -> bool:
        c, _, _ = self.shell("am", "force-stop", package)
        return c == 0

    def tap(self, x: int, y: int) -> bool:
        c, _, _ = self.shell("input", "tap", str(x), str(y))
        return c == 0

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> bool:
        c, _, _ = self.shell(
            "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms)
        )
        return c == 0

    def key(self, keycode: str) -> bool:
        c, _, _ = self.shell("input", "keyevent", keycode)
        return c == 0

    def screencap(self, dest: Path) -> bool:
        dest = Path(dest)
        remote = "/sdcard/forgeos_hud.png"
        c1, _, e1 = self.shell("screencap", "-p", remote, timeout=20)
        if c1 != 0:
            log.warning("screencap failed %s", e1)
            return False
        c2, _, e2 = self.run("pull", remote, str(dest), timeout=30)
        self.shell("rm", remote)
        return c2 == 0 and dest.exists()

    def getprop(self, prop: str) -> str:
        _, out, _ = self.shell("getprop", prop)
        return out

    def optimize_for_film(self) -> dict:
        """Camera/film oriented ADB side (screen + power)."""
        res = {}
        res["screen_on"] = self.screen_on()
        res["keep_awake"] = self.keep_awake(True)
        res["brightness"] = self.brightness(220)
        # disable animations for snappier UI (optional)
        self.shell("settings", "put", "global", "window_animation_scale", "0.5")
        self.shell("settings", "put", "global", "transition_animation_scale", "0.5")
        res["launch_ip_webcam"] = self.launch_ip_webcam()
        time.sleep(1.5)
        return res

    def status_dict(self) -> dict:
        devs = self.devices()
        model = ""
        batt = ""
        if self.is_connected():
            model = self.getprop("ro.product.model")
            _, batt, _ = self.shell("dumpsys", "battery")
            for line in batt.splitlines():
                if "level" in line.lower():
                    batt = line.strip()
                    break
        return {
            "adb": self.adb_path,
            "serial": self.serial,
            "devices": devs,
            "connected": self.is_connected(),
            "model": model,
            "battery": batt[:80] if batt else "",
        }
