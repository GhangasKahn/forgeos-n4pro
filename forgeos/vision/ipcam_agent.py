#!/usr/bin/env python3
"""IP Cam Agent — sole operator/monitor for Android IP Webcam (phone eyes).

Does NOT talk to the printer. Only:
  • health-checks the stream
  • grabs snapshots on an interval
  • optional autofocus / torch / quality maintenance
  • reconnects after dropouts
  • writes status journal + latest JPEG

Run:
  python3 -m forgeos.vision.ipcam_agent --url http://192.168.1.250:8080
  python3 -m forgeos.vision.ipcam_agent --url http://192.168.1.250:8080 --torch-auto
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

from forgeos.vision.phone_camera import PhoneCameraSource, grab_phone_frame
from forgeos.vision.phone_control import PhoneControl

log = logging.getLogger("forgeos.ipcam_agent")

_STOP = False


def _handle_sig(*_a: Any) -> None:
    global _STOP
    _STOP = True
    log.info("stop requested")


@dataclass
class AgentStats:
    started_ts: float = field(default_factory=time.time)
    ticks: int = 0
    ok_ticks: int = 0
    fail_ticks: int = 0
    consecutive_fails: int = 0
    last_ok_ts: float = 0.0
    last_error: str = ""
    last_jpeg_bytes: int = 0
    last_width: int = 0
    last_height: int = 0
    last_coverage: float = 0.0
    last_mean_luma: float = 0.0
    reconnects: int = 0
    focus_pulses: int = 0
    torch_on: bool = False

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["uptime_s"] = round(time.time() - self.started_ts, 1)
        d["ok_rate"] = round(self.ok_ticks / max(1, self.ticks), 3)
        return d


class IPCamAgent:
    """Dedicated camera ops loop."""

    def __init__(
        self,
        url: str,
        *,
        interval_s: float = 1.0,
        snapshot_every: int = 1,
        focus_every_s: float = 45.0,
        torch_auto: bool = False,
        torch_on_below_luma: float = 55.0,
        torch_off_above_luma: float = 90.0,
        quality: int = 70,
        out_dir: Optional[Path] = None,
        fail_reconnect_after: int = 3,
    ) -> None:
        self.url = url.rstrip("/")
        self.interval_s = max(0.2, float(interval_s))
        self.snapshot_every = max(1, int(snapshot_every))
        self.focus_every_s = float(focus_every_s)
        self.torch_auto = bool(torch_auto)
        self.torch_on_below_luma = float(torch_on_below_luma)
        self.torch_off_above_luma = float(torch_off_above_luma)
        self.quality = int(quality)
        self.out_dir = out_dir or (ROOT / "artifacts" / "ipcam_agent")
        self.fail_reconnect_after = max(1, int(fail_reconnect_after))

        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.control = PhoneControl(self.url)
        self.source = PhoneCameraSource(
            self.url, save_dir=str(self.out_dir), timeout_s=3.0
        )
        self.stats = AgentStats()
        self._last_focus_ts = 0.0
        self._optimized = False

    def bootstrap(self) -> None:
        log.info("bootstrap optimize-for-bed url=%s", self.url)
        try:
            res = self.control.optimize_for_bed()
            self.control.quality(self.quality)
            log.info("optimize result %s", res)
            self._optimized = True
        except Exception as exc:  # noqa: BLE001
            log.warning("bootstrap optimize failed: %s", exc)
        ping = self.source.ping()
        log.info("ping %s", ping)
        if not ping.get("ok"):
            log.warning("camera not reachable yet — will keep trying")

    def _write_status(self) -> None:
        path = self.out_dir / "status.json"
        payload = {
            "url": self.url,
            "ts": time.time(),
            "stats": self.stats.as_dict(),
            "torch_auto": self.torch_auto,
            "optimized": self._optimized,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        journal = self.out_dir / "journal.jsonl"
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def _maintain_optics(self, mean_luma: float) -> None:
        now = time.time()
        # periodic AF
        if self.focus_every_s > 0 and (now - self._last_focus_ts) >= self.focus_every_s:
            if self.control.focus(True):
                self.stats.focus_pulses += 1
                self._last_focus_ts = now
                log.info("autofocus pulse #%d", self.stats.focus_pulses)

        if not self.torch_auto:
            return
        # simple luma hysteresis for torch
        if mean_luma < self.torch_on_below_luma and not self.stats.torch_on:
            if self.control.torch(True):
                self.stats.torch_on = True
                log.info("torch ON (luma=%.1f)", mean_luma)
        elif mean_luma > self.torch_off_above_luma and self.stats.torch_on:
            if self.control.torch(False):
                self.stats.torch_on = False
                log.info("torch OFF (luma=%.1f)", mean_luma)

    def _reconnect(self) -> None:
        self.stats.reconnects += 1
        log.warning("reconnect #%d — re-optimize + focus", self.stats.reconnects)
        try:
            self.control.optimize_for_bed()
            self.control.quality(self.quality)
            self.control.focus(True)
            self._last_focus_ts = time.time()
        except Exception as exc:  # noqa: BLE001
            log.warning("reconnect control failed: %s", exc)

    def tick(self) -> bool:
        """One monitor cycle. Returns True if frame OK."""
        self.stats.ticks += 1
        try:
            fr = grab_phone_frame(self.url, timeout_s=3.5)
            rows = fr.gray_rows or [0.0]
            mean_luma = sum(rows) / max(1, len(rows))

            self.stats.ok_ticks += 1
            self.stats.consecutive_fails = 0
            self.stats.last_ok_ts = time.time()
            self.stats.last_error = ""
            self.stats.last_jpeg_bytes = len(fr.jpeg)
            self.stats.last_width = fr.width
            self.stats.last_height = fr.height
            self.stats.last_coverage = fr.coverage
            self.stats.last_mean_luma = mean_luma

            if self.stats.ticks % self.snapshot_every == 0:
                (self.out_dir / "latest.jpg").write_bytes(fr.jpeg)
                # rolling hourly-ish copy every 60 ok frames
                if self.stats.ok_ticks % 60 == 0:
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    (self.out_dir / ("snap_%s.jpg" % stamp)).write_bytes(fr.jpeg)

            self._maintain_optics(mean_luma)
            self._write_status()

            if self.stats.ticks % 10 == 0:
                log.info(
                    "ok tick=%d %dx%d luma=%.0f cov=%.2f fails=%d torch=%s",
                    self.stats.ticks,
                    fr.width,
                    fr.height,
                    mean_luma,
                    fr.coverage,
                    self.stats.fail_ticks,
                    self.stats.torch_on,
                )
            return True
        except Exception as exc:  # noqa: BLE001
            self.stats.fail_ticks += 1
            self.stats.consecutive_fails += 1
            self.stats.last_error = str(exc)
            log.warning(
                "FAIL tick=%d consec=%d err=%s",
                self.stats.ticks,
                self.stats.consecutive_fails,
                exc,
            )
            self._write_status()
            if self.stats.consecutive_fails >= self.fail_reconnect_after:
                self._reconnect()
                self.stats.consecutive_fails = 0
            return False

    def run(self, max_ticks: Optional[int] = None) -> int:
        signal.signal(signal.SIGINT, _handle_sig)
        signal.signal(signal.SIGTERM, _handle_sig)
        self.bootstrap()
        log.info(
            "IP Cam Agent running url=%s interval=%.2fs torch_auto=%s out=%s",
            self.url,
            self.interval_s,
            self.torch_auto,
            self.out_dir,
        )
        n = 0
        while not _STOP:
            t0 = time.time()
            self.tick()
            n += 1
            if max_ticks is not None and n >= max_ticks:
                break
            dt = time.time() - t0
            time.sleep(max(0.0, self.interval_s - dt))
        log.info("agent stopped stats=%s", self.stats.as_dict())
        self._write_status()
        return 0 if self.stats.ok_ticks > 0 else 1


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="IP Cam Agent — phone camera only")
    ap.add_argument(
        "--url",
        default=None,
        help="IP Webcam base URL (default from configs/vision_rig.yaml)",
    )
    ap.add_argument("--interval", type=float, default=1.0, help="monitor period seconds")
    ap.add_argument("--snapshot-every", type=int, default=1, help="save latest.jpg every N ticks")
    ap.add_argument("--focus-every", type=float, default=45.0, help="autofocus period seconds (0=off)")
    ap.add_argument("--torch-auto", action="store_true", help="auto torch from scene luma")
    ap.add_argument("--quality", type=int, default=70)
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "ipcam_agent",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    url = args.url
    if not url:
        cfg_path = ROOT / "configs" / "vision_rig.yaml"
        if cfg_path.exists():
            try:
                import yaml

                cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                url = (cfg.get("phone_camera") or {}).get("url")
            except Exception:  # noqa: BLE001
                url = None
    if not url:
        url = "http://192.168.1.250:8080"
        log.warning("no url configured — defaulting to %s", url)

    agent = IPCamAgent(
        url,
        interval_s=args.interval,
        snapshot_every=args.snapshot_every,
        focus_every_s=args.focus_every,
        torch_auto=args.torch_auto,
        quality=args.quality,
        out_dir=args.out,
    )
    return agent.run(max_ticks=args.max_ticks)


if __name__ == "__main__":
    raise SystemExit(main())
