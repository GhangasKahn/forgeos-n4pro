#!/usr/bin/env python3
"""Commence all film agents + open live agent HUD on the phone.

  python3 scripts/commence_agents_phone_hud.py
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ADB = str(Path.home() / ".local/platform-tools/adb")
if not Path(ADB).exists():
    ADB = "adb"

MAC_IP = "192.168.1.140"
HUD_PORT = 8787
PHONE_HUD = "http://%s:%d/agents" % (MAC_IP, HUD_PORT)
SERIAL_FILE = ROOT / "artifacts" / "film_cam" / "adb_serial.txt"


def mac_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.178", 1))
        return s.getsockname()[0]
    finally:
        s.close()


def adb_serial() -> str:
    if SERIAL_FILE.exists():
        return SERIAL_FILE.read_text(encoding="utf-8").strip()
    out = subprocess.check_output([ADB, "devices"], text=True)
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return ""


def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def kill_old():
    out = subprocess.check_output(["ps", "ax", "-o", "pid=,command="], text=True)
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_s, _, cmd = line.partition(" ")
        cmd = cmd.strip()
        if any(
            x in cmd
            for x in (
                "forgeos.swarm",
                "hud_server",
                "film_cam_agent",
                "ipcam_agent",
            )
        ):
            if "commence_agents" in cmd or "ps ax" in cmd:
                continue
            try:
                os.kill(int(pid_s), signal.SIGTERM)
                print("stopped", pid_s, cmd[:90], flush=True)
            except Exception as exc:
                print("kill", pid_s, exc, flush=True)


def main() -> int:
    global PHONE_HUD
    ip = mac_ip()
    PHONE_HUD = "http://%s:%d/agents" % (ip, HUD_PORT)
    print("MAC_IP", ip, "PHONE_HUD", PHONE_HUD, flush=True)

    kill_old()
    time.sleep(1)

    # never sleep + prepare phone
    serial = adb_serial()
    print("ADB serial", serial, flush=True)
    if serial:
        env = os.environ.copy()
        env["PATH"] = str(Path.home() / ".local/platform-tools") + ":" + env.get("PATH", "")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "phone_never_sleep.py"), "--serial", serial],
            cwd=str(ROOT),
        )
        subprocess.run([ADB, "-s", serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP"])
        subprocess.run(
            [ADB, "-s", serial, "shell", "monkey", "-p", "com.pas.webcam",
             "-c", "android.intent.category.LAUNCHER", "1"]
        )

    # start HUD
    hud = subprocess.Popen(
        [sys.executable, "-u", "-m", "forgeos.vision.hud_server", "--port", str(HUD_PORT)],
        cwd=str(ROOT),
        stdout=open(ROOT / "artifacts" / "film_swarm" / "hud.log", "a"),
        stderr=subprocess.STDOUT,
    )
    print("HUD pid", hud.pid, flush=True)
    time.sleep(1.2)

    # start swarm
    swarm = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "forgeos.swarm",
            "--phone-url",
            "http://192.168.1.250:8080",
            "--adb-serial",
            serial or "192.168.1.250:35853",
            "-v",
        ],
        cwd=str(ROOT),
        stdout=open(ROOT / "artifacts" / "film_swarm" / "swarm.log", "a"),
        stderr=subprocess.STDOUT,
    )
    print("SWARM pid", swarm.pid, flush=True)
    time.sleep(1.0)

    # open agent HUD on phone browser
    if serial:
        # Chrome stable
        for component in (
            "com.android.chrome/com.google.android.apps.chrome.Main",
            "com.chrome.beta/com.google.android.apps.chrome.Main",
            "com.android.chrome/com.google.android.apps.chrome.IntentDispatcher",
        ):
            r = subprocess.run(
                [
                    ADB,
                    "-s",
                    serial,
                    "shell",
                    "am",
                    "start",
                    "-n",
                    component,
                    "-a",
                    "android.intent.action.VIEW",
                    "-d",
                    PHONE_HUD,
                ],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and "Error" not in (r.stderr or ""):
                print("opened chrome", component, flush=True)
                break
        else:
            subprocess.run(
                [
                    ADB,
                    "-s",
                    serial,
                    "shell",
                    "am",
                    "start",
                    "-a",
                    "android.intent.action.VIEW",
                    "-d",
                    PHONE_HUD,
                ]
            )
            print("opened default VIEW intent", flush=True)

    print("\n=== AGENTS COMMENCED ===", flush=True)
    print("Phone HUD:", PHONE_HUD, flush=True)
    print("Mac HUD:  http://127.0.0.1:%d/" % HUD_PORT, flush=True)
    print("Agents:   http://127.0.0.1:%d/agents" % HUD_PORT, flush=True)
    print("Keep phone on this page for IRT agent status.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
