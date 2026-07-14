#!/usr/bin/env python3
"""Film/Cam optimization agent for printer vision.

Combines:
  • ADB full device control (when paired)
  • IP Webcam HTTP camera control (always when server up)
  • Continuous frame grab + film presets (exposure/focus/torch/quality)
  • Writes HUD state for the live dashboard

  python3 -m forgeos.vision.film_cam_agent --ip 192.168.1.250 --http-port 8080
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forgeos.vision.adb_phone import AdbPhone, find_adb
from forgeos.vision.phone_camera import grab_phone_frame
from forgeos.vision.phone_control import PhoneControl

log = logging.getLogger("forgeos.film_cam")
_STOP = False


def _sig(*_a: Any) -> None:
    global _STOP
    _STOP = True


@dataclass
class FilmStats:
    ticks: int = 0
    ok: int = 0
    fail: int = 0
    adb_ok: bool = False
    http_ok: bool = False
    last_error: str = ""
    last_jpeg: int = 0
    last_luma: float = 0.0
    torch: bool = False
    preset: str = "printer_bed"
    started: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["uptime_s"] = round(time.time() - self.started, 1)
        d["ok_rate"] = round(self.ok / max(1, self.ticks), 3)
        return d


class FilmCamAgent:
    """Specialized agent: camera + film optimization for 3D printer monitoring."""

    PRESETS = {
        "printer_bed": {
            "quality": 75,
            "torch_auto": True,
            "torch_on_luma": 50,
            "torch_off_luma": 95,
            "focus_every_s": 25,
            "interval_s": 0.6,
            "brightness": 220,
        },
        "closeup": {
            "quality": 90,
            "torch_auto": True,
            "torch_on_luma": 60,
            "torch_off_luma": 110,
            "focus_every_s": 12,
            "interval_s": 0.5,
            "brightness": 240,
        },
        "wide_chamber": {
            "quality": 60,
            "torch_auto": False,
            "torch_on_luma": 40,
            "torch_off_luma": 80,
            "focus_every_s": 40,
            "interval_s": 0.8,
            "brightness": 180,
        },
    }

    def __init__(
        self,
        ip: str,
        http_port: int = 8080,
        adb_serial: Optional[str] = None,
        preset: str = "printer_bed",
        out_dir: Optional[Path] = None,
    ) -> None:
        self.ip = ip
        self.http_port = http_port
        self.http_url = "http://%s:%d" % (ip, http_port)
        self.out_dir = out_dir or (ROOT / "artifacts" / "film_cam")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.preset_name = preset if preset in self.PRESETS else "printer_bed"
        self.cfg = dict(self.PRESETS[self.preset_name])
        self.stats = FilmStats(preset=self.preset_name)
        self.http = PhoneControl(self.http_url, timeout_s=4.0)
        self.adb: Optional[AdbPhone] = None
        try:
            find_adb()
            self.adb = AdbPhone(serial=adb_serial)
        except FileNotFoundError:
            log.warning("adb binary missing")
        self._last_focus = 0.0

    def try_adb_connect(self, ports: Optional[list] = None) -> bool:
        if not self.adb:
            return False
        # if already have devices
        devs = self.adb.devices()
        if devs:
            self.adb.serial = devs[0]
            self.stats.adb_ok = True
            log.info("ADB already connected: %s", devs)
            return True
        ports = ports or [5555]
        for p in ports:
            ok, msg = self.adb.connect("%s:%d" % (self.ip, p))
            log.info("adb connect %s:%s -> %s %s", self.ip, p, ok, msg)
            if ok:
                self.stats.adb_ok = True
                return True
        self.stats.adb_ok = False
        return False

    def bootstrap(self) -> None:
        log.info("FilmCam bootstrap preset=%s http=%s", self.preset_name, self.http_url)
        self.try_adb_connect()
        if self.adb and self.adb.is_connected():
            try:
                r = self.adb.optimize_for_film()
                log.info("ADB film optimize: %s", r)
                ns = self.adb.never_sleep()
                log.info("ADB never_sleep: %s", ns)
            except Exception as exc:  # noqa: BLE001
                log.warning("ADB optimize failed: %s", exc)
        # HTTP camera side
        for i in range(15):
            try:
                fr = grab_phone_frame(self.http_url, timeout_s=4, decode=False, retries=2)
                self.stats.http_ok = True
                log.info("HTTP cam ONLINE %dx%d", fr.width, fr.height)
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("HTTP wait %d: %s", i + 1, exc)
                # if ADB, try relaunch IP Webcam
                if self.adb and self.adb.is_connected() and i % 3 == 2:
                    self.adb.launch_ip_webcam()
                    self.adb.screen_on()
                time.sleep(1.0)
        try:
            self.http.optimize_for_bed()
            self.http.quality(int(self.cfg["quality"]))
            self.http.focus(True)
        except Exception as exc:  # noqa: BLE001
            log.warning("HTTP optimize: %s", exc)

    def set_preset(self, name: str) -> None:
        if name in self.PRESETS:
            self.preset_name = name
            self.cfg = dict(self.PRESETS[name])
            self.stats.preset = name
            self.http.quality(int(self.cfg["quality"]))
            if self.adb and self.adb.is_connected():
                self.adb.brightness(int(self.cfg.get("brightness", 200)))
            log.info("preset -> %s", name)

    def _write_hud_state(self, extra: Optional[dict] = None) -> None:
        adb_st = self.adb.status_dict() if self.adb else {"connected": False}
        payload = {
            "ts": time.time(),
            "http_url": self.http_url,
            "preset": self.preset_name,
            "cfg": self.cfg,
            "stats": self.stats.as_dict(),
            "adb": adb_st,
            "latest_jpg": str(self.out_dir / "latest.jpg"),
            "screen_png": str(self.out_dir / "screen.png"),
            "extra": extra or {},
        }
        (self.out_dir / "hud_state.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        with (self.out_dir / "journal.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        (self.out_dir / "LIVE").write_text(
            "%s http=%s adb=%s ok_rate=%.2f ticks=%d preset=%s\n"
            % (
                "ONLINE" if self.stats.http_ok else "OFFLINE",
                self.stats.http_ok,
                self.stats.adb_ok,
                self.stats.ok / max(1, self.stats.ticks),
                self.stats.ticks,
                self.preset_name,
            ),
            encoding="utf-8",
        )

    def tick(self) -> None:
        self.stats.ticks += 1
        # ADB keep-awake + occasional screencap for true phone HUD
        if self.adb and self.adb.is_connected():
            self.stats.adb_ok = True
            if self.stats.ticks % 10 == 1:
                try:
                    self.adb.never_sleep()
                except Exception as exc:  # noqa: BLE001
                    log.debug("never_sleep: %s", exc)
            if self.stats.ticks % 8 == 1:
                try:
                    self.adb.screencap(self.out_dir / "screen.png")
                except Exception as exc:  # noqa: BLE001
                    log.debug("screencap: %s", exc)

        try:
            fr = grab_phone_frame(
                self.http_url, timeout_s=5.0, decode=(self.stats.ticks % 4 == 1), retries=4
            )
            self.stats.ok += 1
            self.stats.http_ok = True
            self.stats.last_jpeg = len(fr.jpeg)
            self.stats.last_error = ""
            (self.out_dir / "latest.jpg").write_bytes(fr.jpeg)
            if fr.gray_rows:
                self.stats.last_luma = sum(fr.gray_rows) / len(fr.gray_rows)

            # film optics
            now = time.time()
            if now - self._last_focus >= float(self.cfg["focus_every_s"]):
                self.http.focus(True)
                self._last_focus = now

            if self.cfg.get("torch_auto"):
                luma = self.stats.last_luma
                if luma and luma < float(self.cfg["torch_on_luma"]) and not self.stats.torch:
                    self.http.torch(True)
                    self.stats.torch = True
                elif luma and luma > float(self.cfg["torch_off_luma"]) and self.stats.torch:
                    self.http.torch(False)
                    self.stats.torch = False

            if self.stats.ticks % 5 == 0:
                log.info(
                    "FILM tick=%d ok_rate=%.2f jpeg=%d luma=%.0f torch=%s adb=%s",
                    self.stats.ticks,
                    self.stats.ok / max(1, self.stats.ticks),
                    self.stats.last_jpeg,
                    self.stats.last_luma,
                    self.stats.torch,
                    self.stats.adb_ok,
                )
        except Exception as exc:  # noqa: BLE001
            self.stats.fail += 1
            self.stats.http_ok = False
            self.stats.last_error = str(exc)
            log.warning("FILM OFFLINE %s", exc)
            if self.adb and self.adb.is_connected() and self.stats.fail % 3 == 0:
                self.adb.screen_on()
                self.adb.launch_ip_webcam()

        self._write_hud_state()

    def run(self, max_ticks: Optional[int] = None) -> int:
        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
        self.bootstrap()
        n = 0
        interval = float(self.cfg["interval_s"])
        while not _STOP:
            t0 = time.time()
            self.tick()
            n += 1
            if max_ticks and n >= max_ticks:
                break
            time.sleep(max(0.0, interval - (time.time() - t0)))
        return 0 if self.stats.ok else 1


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Film/Cam agent for printer monitoring")
    ap.add_argument("--ip", default="192.168.1.250")
    ap.add_argument("--http-port", type=int, default=8080)
    ap.add_argument("--adb-serial", default=None, help="e.g. 192.168.1.250:40555 after pair")
    ap.add_argument("--preset", default="printer_bed", choices=sorted(FilmCamAgent.PRESETS))
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    agent = FilmCamAgent(
        args.ip,
        http_port=args.http_port,
        adb_serial=args.adb_serial,
        preset=args.preset,
    )
    return agent.run(max_ticks=args.max_ticks)


if __name__ == "__main__":
    raise SystemExit(main())
