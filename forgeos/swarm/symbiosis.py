"""Symbiosis bridge — Grok session ↔ film swarm agents.

Shared protocol files under artifacts/film_swarm/:

  GROK_OUTBOX.jsonl   — Grok (or human) writes commands for agents
  GROK_INBOX.jsonl    — agents write events/status for Grok to read
  SYMBIOSIS.json      — live snapshot both sides refresh
  COMMANDS.json       — last command (simple one-shot)

Command schema (outbox line or COMMANDS.json):
  {"cmd": "burst", "count": 12, "ts": ...}
  {"cmd": "closeup"}
  {"cmd": "focus"}
  {"cmd": "torch", "on": true}
  {"cmd": "scene", "scene": "closeup"|"printer_bed"|"wide"}
  {"cmd": "test", "suite": "capture"|"optics"|"full"}
  {"cmd": "status"}
  {"cmd": "prompt", "text": "..."}  # re-broadcast operator prompt

Inbox events:
  film.*, swarm.*, symbiosis.test_result, etc.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from forgeos.swarm.bus import MessageBus
from forgeos.swarm.orchestrator import FilmSwarm

ROOT = Path(__file__).resolve().parents[2]
SWARM = ROOT / "artifacts" / "film_swarm"
OUTBOX = SWARM / "GROK_OUTBOX.jsonl"
INBOX = SWARM / "GROK_INBOX.jsonl"
SNAP = SWARM / "SYMBIOSIS.json"
COMMANDS = SWARM / "COMMANDS.json"

log = logging.getLogger("swarm.symbiosis")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def grok_emit(cmd: str, **payload: Any) -> dict:
    """Grok-side: write a command for the swarm (call from tools/scripts)."""
    row = {"cmd": cmd, "ts": time.time(), **payload}
    _append_jsonl(OUTBOX, row)
    COMMANDS.write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def grok_read_inbox(n: int = 40) -> List[dict]:
    """Grok-side: read latest agent messages."""
    if not INBOX.exists():
        return []
    lines = INBOX.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def grok_status() -> dict:
    if SNAP.exists():
        try:
            return json.loads(SNAP.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"error": "no SYMBIOSIS.json yet — is bridge running?"}


class SymbiosisBridge:
    """Binds a FilmSwarm bus to disk so Grok can sync without sharing process memory."""

    def __init__(self, swarm: FilmSwarm) -> None:
        self.swarm = swarm
        self.bus = swarm.bus
        self._outbox_pos = 0
        SWARM.mkdir(parents=True, exist_ok=True)
        # seed offsets at EOF
        if OUTBOX.exists():
            self._outbox_pos = OUTBOX.stat().st_size
        # mirror all bus traffic into inbox (filtered)
        self.bus.subscribe("*", self._mirror_to_inbox)

    def _mirror_to_inbox(self, msg) -> None:
        # skip high-frequency noise
        if msg.topic in ("film.printer.telemetry", "film.director.heartbeat"):
            if int(msg.ts) % 5 != 0:
                return
        row = msg.as_dict()
        row["symbiosis"] = True
        _append_jsonl(INBOX, row)

    def poll_outbox(self) -> List[dict]:
        """Read new Grok commands and dispatch to bus."""
        if not OUTBOX.exists():
            return []
        data = OUTBOX.read_bytes()
        if self._outbox_pos > len(data):
            self._outbox_pos = 0
        chunk = data[self._outbox_pos :].decode("utf-8", errors="replace")
        self._outbox_pos = len(data)
        cmds = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except Exception:
                continue
            cmds.append(cmd)
            self.dispatch(cmd)
        # also accept COMMANDS.json overwrite
        if COMMANDS.exists():
            try:
                c = json.loads(COMMANDS.read_text(encoding="utf-8"))
                # only if fresh (< 3s) and not already processed this second
                if time.time() - float(c.get("ts") or 0) < 2.5:
                    # avoid double if same as last outbox line
                    if not cmds or cmds[-1] != c:
                        self.dispatch(c)
                        cmds.append(c)
            except Exception:
                pass
        return cmds

    def dispatch(self, cmd: dict) -> None:
        name = str(cmd.get("cmd") or "").lower()
        log.info("dispatch %s %s", name, cmd)
        self.bus.emit(
            "symbiosis.command",
            "grok",
            cmd,
        )
        if name == "burst":
            self.bus.emit(
                "film.burst",
                "grok",
                {"count": int(cmd.get("count", 12)), "reason": "grok"},
            )
        elif name == "closeup":
            self.bus.emit("film.director.cue", "grok", {"cue": "closeups_needed"})
            self.bus.emit("film.scene", "grok", {"scene": "closeup", "reason": "grok"})
        elif name == "focus":
            self.bus.emit("film.optics.focus", "grok", {})
        elif name == "torch":
            self.bus.emit(
                "film.optics.torch", "grok", {"on": bool(cmd.get("on", True))}
            )
        elif name == "scene":
            self.bus.emit(
                "film.scene",
                "grok",
                {"scene": cmd.get("scene", "printer_bed"), "reason": "grok"},
            )
        elif name == "shot":
            self.bus.emit(
                "film.shot", "grok", {"tag": cmd.get("tag", "grok_shot")}
            )
        elif name == "test":
            self._run_test(str(cmd.get("suite", "full")))
        elif name == "status":
            self._write_snap(extra={"status_requested": True})
        elif name == "prompt":
            self.bus.emit(
                "film.operator.prompt",
                "grok",
                {"text": cmd.get("text", "")},
            )
        elif name == "adb":
            self.bus.emit("film.adb", "grok", {"op": cmd.get("op", "wake")})
        else:
            self.bus.emit("swarm.command", "grok", {"cmd": name, "target": "*", **cmd})

    def _run_test(self, suite: str) -> None:
        results = {"suite": suite, "ts": time.time(), "steps": []}
        if suite in ("capture", "full"):
            self.bus.emit("film.burst", "grok", {"count": 5, "reason": "test_capture"})
            results["steps"].append({"step": "burst5", "ok": True})
        if suite in ("optics", "full"):
            self.bus.emit("film.optics.focus", "grok", {})
            self.bus.emit("film.scene", "grok", {"scene": "printer_bed"})
            results["steps"].append({"step": "optics", "ok": True})
        if suite in ("closeup", "full"):
            self.bus.emit("film.director.cue", "grok", {"cue": "closeups_needed"})
            results["steps"].append({"step": "closeup_cue", "ok": True})
        # capture path check after short wait done by bridge tick
        results["latest_exists"] = (SWARM / "latest.jpg").exists() or (
            SWARM / "frames" / "latest.jpg"
        ).exists()
        self.bus.emit("symbiosis.test_result", "symbiosis", results)
        _append_jsonl(INBOX, {"topic": "symbiosis.test_result", "payload": results, "ts": time.time()})
        self._write_snap(extra={"last_test": results})

    def _write_snap(self, extra: Optional[dict] = None) -> None:
        recent = self.bus.recent(40)
        snap = {
            "ts": time.time(),
            "agents": [a.name for a in self.swarm.agents],
            "phone": self.swarm.phone_url,
            "recent_topics": [m.get("topic") for m in recent[-15:]],
            "recent": recent[-20:],
            "live": (SWARM / "LIVE").read_text(encoding="utf-8")
            if (SWARM / "LIVE").exists()
            else "",
            "swarm_live": (SWARM / "SWARM_LIVE").read_text(encoding="utf-8")
            if (SWARM / "SWARM_LIVE").exists()
            else "",
            "latest_jpg": str(SWARM / "latest.jpg"),
            "inbox_tail": grok_read_inbox(8),
            "extra": extra or {},
        }
        SNAP.write_text(json.dumps(snap, indent=2), encoding="utf-8")

    def tick(self) -> None:
        self.poll_outbox()
        self._write_snap()


def write_and_wait(cmd: str, wait_s: float = 2.0, **payload: Any) -> dict:
    """Helper for Grok tool runs: emit command, brief wait, return status."""
    row = grok_emit(cmd, **payload)
    time.sleep(wait_s)
    return {"sent": row, "status": grok_status(), "inbox": grok_read_inbox(15)}
