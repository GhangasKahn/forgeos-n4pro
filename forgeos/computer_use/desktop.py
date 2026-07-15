"""Desktop control via xdotool + screenshots on DISPLAY=:1 (TigerVNC/XFCE)."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class Desktop:
    display: str = ":1"
    artifact_dir: Path = Path("/opt/cursor/artifacts/computer_use")

    def __post_init__(self) -> None:
        self.artifact_dir = Path(self.artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("DISPLAY", self.display)

    def _env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def run(self, *args: str, check: bool = True, timeout: float = 30.0) -> subprocess.CompletedProcess:
        return subprocess.run(
            list(args),
            env=self._env(),
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def screenshot(self, name: str = "screen") -> Path:
        """Grab full desktop; return PNG path."""
        out = self.artifact_dir / ("%s_%d.png" % (name, int(time.time() * 1000)))
        # Prefer scrot; fall back to mss via python
        try:
            self.run("scrot", "-o", str(out))
            return out
        except (subprocess.CalledProcessError, FileNotFoundError):
            import mss
            from PIL import Image

            with mss.mss() as sct:
                # monitor 1 under DISPLAY
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                shot = sct.grab(mon)
                Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX").save(out)
            return out

    def mouse_move(self, x: int, y: int) -> None:
        self.run("xdotool", "mousemove", "--sync", str(x), str(y))

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: int = 1) -> None:
        if x is not None and y is not None:
            self.mouse_move(x, y)
        self.run("xdotool", "click", str(button))

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        if x is not None and y is not None:
            self.mouse_move(x, y)
        self.run("xdotool", "click", "--repeat", "2", "--delay", "80", "1")

    def type_text(self, text: str, delay_ms: int = 12) -> None:
        # Use --clearmodifiers; escape for xdotool type
        self.run("xdotool", "type", "--clearmodifiers", "--delay", str(delay_ms), "--", text)

    def key(self, *keys: str) -> None:
        """Send keystroke combo, e.g. key('ctrl+l') or key('Return')."""
        self.run("xdotool", "key", "--clearmodifiers", *keys)

    def get_mouse(self) -> Tuple[int, int]:
        out = self.run("xdotool", "getmouselocation", "--shell").stdout
        vals = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k] = int(v)
        return vals.get("X", 0), vals.get("Y", 0)

    def window_list(self) -> str:
        try:
            return self.run("wmctrl", "-l").stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self.run("xdotool", "search", "--name", ".", "getwindowname", "%@").stdout

    def focus_window(self, name_substr: str) -> bool:
        try:
            self.run("wmctrl", "-a", name_substr)
            return True
        except subprocess.CalledProcessError:
            return False

    def launch(self, *cmd: str) -> subprocess.Popen:
        return subprocess.Popen(list(cmd), env=self._env(), start_new_session=True)

    def open_chrome(self, url: str = "about:blank") -> None:
        self.launch(
            "google-chrome",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--window-size=1600,1000",
            url,
        )
        time.sleep(2.0)

    def chrome_goto(self, url: str) -> None:
        """Focus Chrome omnibox and navigate (best-effort)."""
        self.focus_window("Chrome") or self.focus_window("Chromium")
        time.sleep(0.3)
        self.key("ctrl+l")
        time.sleep(0.2)
        self.type_text(url, delay_ms=8)
        self.key("Return")
        time.sleep(1.5)
