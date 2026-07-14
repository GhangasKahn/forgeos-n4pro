"""Real-time dynamic loop — high-rate poll + optional config hot-reload.

Designed to run on Jetson (with cameras later) or any host with Moonraker access.
Fully dynamic: every tick updates adaptive state and re-plans actions.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from forgeos.vision.adaptive_state import AdaptiveState
from forgeos.vision.bus import MoonrakerBus
from forgeos.vision.dynamic_controller import DynamicController, ControlTick
from forgeos.vision.scorers.first_layer import FirstLayerResult, score_from_gray_rows
from forgeos.vision.telemetry_features import (
    default_pack_geometry,
    extract_telemetry,
)


log = logging.getLogger("forgeos.vision.rt")


class RealtimeVisionLoop:
    def __init__(
        self,
        bus: MoonrakerBus,
        *,
        interval_s: float = 0.25,
        armed: bool = False,
        state_path: Optional[Path] = None,
        journal_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
        vision_feature_fn: Optional[Callable[[], Optional[FirstLayerResult]]] = None,
    ) -> None:
        self.bus = bus
        self.interval_s = max(0.05, float(interval_s))
        self.state_path = state_path
        self.journal_path = journal_path
        self.config_path = config_path
        self.vision_feature_fn = vision_feature_fn
        self._cfg_mtime = 0.0
        self._cfg: Dict[str, Any] = {}

        st = AdaptiveState.load(state_path) if state_path else AdaptiveState()
        st.armed = armed
        st.mode = "armed" if armed else "suggest"
        self.controller = DynamicController(st)
        self.geom = default_pack_geometry()
        self._load_config(force=True)

    def _load_config(self, force: bool = False) -> None:
        if not self.config_path or not self.config_path.exists():
            return
        mtime = self.config_path.stat().st_mtime
        if not force and mtime <= self._cfg_mtime:
            return
        try:
            import yaml  # optional

            self._cfg = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            try:
                self._cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log.warning("config reload failed: %s", exc)
                return
        self._cfg_mtime = mtime
        rt = (self._cfg.get("realtime") or {}) if isinstance(self._cfg, dict) else {}
        if "interval_s" in rt:
            self.interval_s = max(0.05, float(rt["interval_s"]))
        pol = self._cfg.get("policy") or {}
        if pol.get("auto_apply") is True:
            self.controller.state.armed = True
            self.controller.state.mode = "armed"
        if "alpha" in rt:
            self.controller.state.alpha = float(rt["alpha"])
        if "min_apply_interval_s" in rt:
            self.controller.state.min_apply_interval_s = float(rt["min_apply_interval_s"])
        log.info("config hot-reloaded interval=%.3f armed=%s", self.interval_s, self.controller.state.armed)

    def _query_status(self) -> Dict[str, Any]:
        names = [
            "print_stats",
            "extruder",
            "heater_bed",
            "toolhead",
            "gcode_move",
            "virtual_sdcard",
            "idle_timeout",
        ]
        return self.bus.objects_query(names)

    def _journal(self, tick: ControlTick) -> None:
        if not self.journal_path:
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(tick.as_dict()) + "\n")

    def tick_once(self) -> ControlTick:
        self._load_config(force=False)
        status = self._query_status()
        tele = extract_telemetry(
            status,
            line_w=self.geom["line_w"],
            layer_h=self.geom["layer_h"],
            spacing_ratio=self.controller.state.spacing_ratio,
            flow=self.controller.state.flow,
        )
        vision = None
        if self.vision_feature_fn is not None:
            try:
                vision = self.vision_feature_fn()
            except Exception as exc:
                log.warning("vision features failed: %s", exc)
        tick = self.controller.plan(tele, vision=vision)
        scripts = self.controller.scripts_to_apply(tick)
        for script in scripts:
            try:
                log.warning("RT APPLY %s", script)
                self.bus.gcode(script)
            except Exception as exc:
                log.error("apply failed %s: %s", script, exc)
        self._journal(tick)
        if self.state_path:
            try:
                self.controller.state.save(self.state_path)
            except Exception as exc:
                log.debug("state save: %s", exc)
        return tick

    def run(self, *, once: bool = False, max_ticks: Optional[int] = None) -> None:
        n = 0
        log.info(
            "RT loop start interval=%.3fs armed=%s moonraker=%s",
            self.interval_s,
            self.controller.state.armed,
            self.bus.base,
        )
        while True:
            t0 = time.time()
            try:
                tick = self.tick_once()
                log.info(
                    "rt tick#%d mode=%s print=%s flat=%.2f rib=%.2f actions=%d z=%.3f",
                    self.controller.state.ticks,
                    tick.mode,
                    tick.features.get("print_state"),
                    tick.quality.get("flat", 0),
                    tick.quality.get("rib", 0),
                    len([a for a in tick.actions if a.kind == "gcode"]),
                    float(tick.features.get("z_adjust_mm") or 0),
                )
            except Exception as exc:
                log.exception("rt tick error: %s", exc)
            n += 1
            if once or (max_ticks is not None and n >= max_ticks):
                break
            dt = time.time() - t0
            time.sleep(max(0.0, self.interval_s - dt))


def placeholder_vision_from_tele_rows(seed: int = 0) -> FirstLayerResult:
    """Deterministic placeholder until cameras attached — still dynamic via tele path."""
    rows = [100 + ((seed + i) % 7) * 3 for i in range(32)]
    return score_from_gray_rows(rows, coverage=0.7)
