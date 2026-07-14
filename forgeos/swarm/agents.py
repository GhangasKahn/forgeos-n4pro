"""Specialized film-swarm agents."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from forgeos.swarm.base import BaseAgent
from forgeos.swarm.bus import Message, MessageBus

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "film_swarm"


class CaptureAgent(BaseAgent):
    """Continuous frame grab — sole HTTP camera consumer when in swarm mode."""

    name = "capture"
    subscriptions = ["film.capture.request", "film.burst", "film.shot"]

    def __init__(self, bus: MessageBus, phone_url: str) -> None:
        super().__init__(bus)
        self.phone_url = phone_url.rstrip("/")
        self.out = OUT / "frames"
        self.out.mkdir(parents=True, exist_ok=True)
        self._n = 0
        self._burst_left = 0
        self._last_ok = 0.0

    def interval_s(self) -> float:
        return 0.35 if self._burst_left > 0 else 0.7

    def on_message(self, msg: Message) -> None:
        if msg.topic == "film.burst":
            self._burst_left = int(msg.payload.get("count", 12))
            self.emit("film.capture.ack", {"burst": self._burst_left})
        elif msg.topic in ("film.capture.request", "film.shot"):
            self._grab(tag=msg.payload.get("tag", "shot"))

    def tick(self) -> None:
        tag = "live"
        if self._burst_left > 0:
            tag = "burst"
            self._burst_left -= 1
        self._grab(tag=tag)

    def _grab(self, tag: str = "live") -> None:
        from forgeos.vision.phone_camera import grab_phone_frame

        try:
            fr = grab_phone_frame(self.phone_url, timeout_s=5, decode=False, retries=3)
            self._n += 1
            self._last_ok = time.time()
            latest = self.out / "latest.jpg"
            latest.write_bytes(fr.jpeg)
            # also mirror for HUD
            (OUT / "latest.jpg").write_bytes(fr.jpeg)
            if tag != "live" or self._n % 15 == 0:
                stamp = time.strftime("%Y%m%d_%H%M%S")
                path = self.out / ("%s_%s_%04d.jpg" % (tag, stamp, self._n))
                path.write_bytes(fr.jpeg)
            self.emit(
                "film.frame",
                {
                    "n": self._n,
                    "bytes": len(fr.jpeg),
                    "w": fr.width,
                    "h": fr.height,
                    "tag": tag,
                    "path": str(latest),
                    "ts": fr.ts,
                },
            )
            (OUT / "LIVE").write_text(
                "CAPTURE ONLINE n=%d %s\n" % (self._n, time.strftime("%H:%M:%S")),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            self.emit("film.capture.fail", {"error": str(exc)})
            (OUT / "LIVE").write_text(
                "CAPTURE OFFLINE %s\n" % exc, encoding="utf-8"
            )


class OpticsAgent(BaseAgent):
    """Focus / torch / quality / film presets."""

    name = "optics"
    subscriptions = [
        "film.frame",
        "film.optics.focus",
        "film.optics.torch",
        "film.optics.preset",
        "film.scene",
    ]

    def __init__(self, bus: MessageBus, phone_url: str) -> None:
        super().__init__(bus)
        self.phone_url = phone_url
        from forgeos.vision.phone_control import PhoneControl

        self.ctrl = PhoneControl(phone_url)
        self._last_focus = 0.0
        self._torch = False
        self._preset = "printer_bed"
        self._luma_ema = 100.0

    def setup(self) -> None:
        try:
            r = self.ctrl.optimize_for_bed()
            self.ctrl.quality(75)
            self.emit("film.optics.ready", {"optimize": r})
        except Exception as exc:  # noqa: BLE001
            self.emit("film.optics.fail", {"error": str(exc)})

    def interval_s(self) -> float:
        return 2.0

    def on_message(self, msg: Message) -> None:
        if msg.topic == "film.optics.focus":
            self.ctrl.focus(True)
            self._last_focus = time.time()
            self.emit("film.optics.event", {"focus": True})
        elif msg.topic == "film.optics.torch":
            on = bool(msg.payload.get("on", True))
            self.ctrl.torch(on)
            self._torch = on
            self.emit("film.optics.event", {"torch": on})
        elif msg.topic == "film.optics.preset":
            self._apply_preset(str(msg.payload.get("name", "printer_bed")))
        elif msg.topic == "film.scene":
            # director says scene type
            scene = str(msg.payload.get("scene", ""))
            if scene in ("closeup", "defect", "first_layer"):
                self._apply_preset("closeup")
            elif scene in ("chamber", "wide"):
                self._apply_preset("wide")
            else:
                self._apply_preset("printer_bed")
        elif msg.topic == "film.frame":
            # optional: director may publish luma later; keep focus cadence
            pass

    def _apply_preset(self, name: str) -> None:
        self._preset = name
        if name == "closeup":
            self.ctrl.quality(90)
            self.ctrl.focus(True)
        elif name == "wide":
            self.ctrl.quality(55)
            self.ctrl.torch(False)
            self._torch = False
        else:
            self.ctrl.optimize_for_bed()
            self.ctrl.quality(75)
        self.emit("film.optics.preset.applied", {"name": name})

    def tick(self) -> None:
        now = time.time()
        if now - self._last_focus > 30:
            try:
                self.ctrl.focus(True)
                self._last_focus = now
                self.emit("film.optics.event", {"focus": "periodic"})
            except Exception as exc:  # noqa: BLE001
                self.emit("film.optics.fail", {"error": str(exc)})


class AdbAgent(BaseAgent):
    """ADB device control when paired."""

    name = "adb"
    subscriptions = ["film.adb", "film.scene", "swarm.command"]

    def __init__(self, bus: MessageBus, serial: Optional[str] = None) -> None:
        super().__init__(bus)
        self.serial = serial
        self.phone = None
        try:
            from forgeos.vision.adb_phone import AdbPhone, find_adb

            find_adb()
            self.phone = AdbPhone(serial=serial)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("ADB unavailable: %s", exc)

    def interval_s(self) -> float:
        return 5.0

    def setup(self) -> None:
        if not self.phone:
            self.emit("film.adb.status", {"connected": False, "reason": "no_adb"})
            return
        devs = self.phone.devices()
        if devs and not self.serial:
            self.phone.serial = devs[0]
        connected = self.phone.is_connected()
        self.emit("film.adb.status", {"connected": connected, "devices": devs})
        if connected:
            try:
                r = self.phone.optimize_for_film()
                self.emit("film.adb.ready", r)
            except Exception as exc:  # noqa: BLE001
                self.emit("film.adb.fail", {"error": str(exc)})

    def on_message(self, msg: Message) -> None:
        if not self.phone or not self.phone.is_connected():
            return
        if msg.topic == "film.adb":
            op = msg.payload.get("op")
            if op == "launch_cam":
                self.phone.launch_ip_webcam()
                self.phone.screen_on()
            elif op == "screencap":
                path = OUT / "screen.png"
                ok = self.phone.screencap(path)
                self.emit("film.adb.screencap", {"ok": ok, "path": str(path)})
            elif op == "wake":
                self.phone.screen_on()
                self.phone.keep_awake(True)
        elif msg.topic == "film.scene" and msg.payload.get("scene") == "closeup":
            self.phone.brightness(240)

    def tick(self) -> None:
        if not self.phone:
            return
        connected = self.phone.is_connected()
        if connected and self.stats_tick():
            path = OUT / "screen.png"
            self.phone.screencap(path)
            self.emit("film.adb.screencap", {"ok": path.exists(), "path": str(path)})

    def stats_tick(self) -> bool:
        # screencap every ~ other tick handled by interval
        return True


class PrinterSenseAgent(BaseAgent):
    """Printer telemetry → film cues (layer change, complete, heating)."""

    name = "printer"
    subscriptions = ["film.printer.poll"]

    def __init__(self, bus: MessageBus, moonraker: str = "http://192.168.1.178:7125") -> None:
        super().__init__(bus)
        self.moonraker = moonraker.rstrip("/")
        self._last_state = ""
        self._last_prog = -1.0

    def interval_s(self) -> float:
        return 2.0

    def tick(self) -> None:
        import urllib.parse
        import urllib.request

        try:
            names = [
                "print_stats",
                "extruder",
                "heater_bed",
                "virtual_sdcard",
                "gcode_move",
            ]
            q = "&".join(urllib.parse.quote(n, safe="") for n in names)
            with urllib.request.urlopen(
                self.moonraker + "/printer/objects/query?" + q, timeout=5
            ) as r:
                st = json.loads(r.read().decode())["result"]["status"]
            ps = st.get("print_stats") or {}
            state = str(ps.get("state") or "")
            prog = float((st.get("virtual_sdcard") or {}).get("progress") or 0)
            e = st.get("extruder") or {}
            payload = {
                "state": state,
                "filename": ps.get("filename"),
                "progress": prog,
                "print_s": ps.get("print_duration"),
                "noz": e.get("temperature"),
                "noz_t": e.get("target"),
                "z": (st.get("gcode_move") or {}).get("homing_origin", [0, 0, 0])[2],
            }
            self.emit("film.printer.telemetry", payload)

            if state != self._last_state:
                self.emit(
                    "film.printer.event",
                    {"event": "state_change", "from": self._last_state, "to": state, **payload},
                )
                if state == "complete":
                    self.emit("film.scene", {"scene": "closeup", "reason": "print_complete"})
                    self.emit("film.burst", {"count": 20, "reason": "print_complete"})
                    self.emit(
                        "film.director.cue",
                        {"cue": "closeups_needed", "filename": payload.get("filename")},
                    )
                if state == "printing" and self._last_state != "printing":
                    self.emit("film.scene", {"scene": "printer_bed", "reason": "print_start"})
                    self.emit("film.burst", {"count": 8, "reason": "print_start"})
                self._last_state = state

            # progress milestones for footage
            for mark in (0.25, 0.5, 0.75, 0.95):
                if self._last_prog < mark <= prog:
                    self.emit(
                        "film.director.cue",
                        {"cue": "milestone", "progress": mark, "filename": payload.get("filename")},
                    )
                    self.emit("film.burst", {"count": 6, "reason": "milestone_%.0f" % (mark * 100)})
            self._last_prog = prog
        except Exception as exc:  # noqa: BLE001
            self.emit("film.printer.fail", {"error": str(exc)})


class ArchiveAgent(BaseAgent):
    """Organize footage into session folders + manifest."""

    name = "archive"
    subscriptions = ["film.frame", "film.director.cue", "film.burst"]

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(bus)
        self.session = time.strftime("session_%Y%m%d_%H%M%S")
        self.dir = OUT / "sessions" / self.session
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self.dir / "manifest.jsonl"
        self._saved = 0

    def interval_s(self) -> float:
        return 10.0

    def on_message(self, msg: Message) -> None:
        if msg.topic == "film.frame" and msg.payload.get("tag") in ("burst", "shot"):
            src = Path(str(msg.payload.get("path") or OUT / "frames" / "latest.jpg"))
            if src.exists():
                dest = self.dir / ("%s_%04d.jpg" % (msg.payload.get("tag"), self._saved))
                dest.write_bytes(src.read_bytes())
                self._saved += 1
                self._log_manifest({"type": "frame", "file": dest.name, **msg.payload})
        elif msg.topic == "film.director.cue":
            self._log_manifest({"type": "cue", **msg.payload})
            cues_path = self.dir / "CUES.txt"
            prev = cues_path.read_text(encoding="utf-8") if cues_path.exists() else ""
            cues_path.write_text(
                prev
                + "\n%s %s\n" % (time.strftime("%H:%M:%S"), json.dumps(msg.payload)),
                encoding="utf-8",
            )

    def _log_manifest(self, row: dict) -> None:
        row = dict(row)
        row["ts"] = time.time()
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def tick(self) -> None:
        self.emit(
            "film.archive.status",
            {"session": self.session, "saved": self._saved, "dir": str(self.dir)},
        )


class DirectorAgent(BaseAgent):
    """Coordinates the swarm for serious footage capture."""

    name = "director"
    subscriptions = [
        "film.printer.event",
        "film.director.cue",
        "film.capture.fail",
        "film.optics.fail",
        "swarm.command",
    ]

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(bus)
        self.mode = "auto_documentary"  # auto_documentary | manual | closeup_session
        self.cues = 0

    def interval_s(self) -> float:
        return 3.0

    def setup(self) -> None:
        self.emit(
            "film.director.hello",
            {
                "mode": self.mode,
                "plan": [
                    "print_start_burst",
                    "milestone_bursts",
                    "optics_track_bed",
                    "print_complete_closeup_session",
                ],
            },
        )
        # opening establishing shot
        self.emit("film.scene", {"scene": "printer_bed", "reason": "director_open"})
        self.emit("film.burst", {"count": 5, "reason": "establishing"})

    def on_message(self, msg: Message) -> None:
        if msg.topic == "film.director.cue":
            self.cues += 1
            cue = msg.payload.get("cue")
            if cue == "closeups_needed":
                self.mode = "closeup_session"
                self.emit("film.scene", {"scene": "closeup", "reason": "director"})
                self.emit("film.optics.focus", {})
                self.emit("film.burst", {"count": 24, "reason": "closeup_session"})
                self.emit(
                    "film.operator.prompt",
                    {
                        "text": "CLOSE-UPS: move phone 10-20cm from part — top, sides, first layer",
                        "filename": msg.payload.get("filename"),
                    },
                )
                # write prompt file
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / "OPERATOR_PROMPT.txt").write_text(
                    "CLOSE-UPS NEEDED\n%s\n%s\n"
                    % (msg.payload.get("filename"), time.strftime("%Y-%m-%d %H:%M:%S")),
                    encoding="utf-8",
                )
        elif msg.topic == "film.capture.fail":
            self.emit("film.adb", {"op": "launch_cam"})
            self.emit("film.adb", {"op": "wake"})
        elif msg.topic == "swarm.command":
            cmd = msg.payload.get("cmd")
            if cmd == "closeup":
                self.emit("film.director.cue", {"cue": "closeups_needed"})
            elif cmd == "burst":
                self.emit("film.burst", {"count": int(msg.payload.get("count", 15))})

    def tick(self) -> None:
        self.emit(
            "film.director.heartbeat",
            {"mode": self.mode, "cues": self.cues, "ts": time.time()},
        )


class CommsAgent(BaseAgent):
    """Status aggregator for HUD / humans."""

    name = "comms"
    subscriptions = ["*"]

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(bus)
        self.state: Dict[str, Any] = {"agents": {}, "last": {}}

    def interval_s(self) -> float:
        return 1.0

    def on_message(self, msg: Message) -> None:
        self.state["last"][msg.topic] = msg.as_dict()
        if msg.topic.startswith("swarm.agent"):
            self.state["agents"][msg.payload.get("agent", msg.sender)] = msg.payload

    def tick(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        snap = {
            "ts": time.time(),
            "recent": self.bus.recent(30),
            "state": self.state,
        }
        (OUT / "swarm_state.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
