#!/usr/bin/env python3
"""Real-time HUD for phone cam + printer + film agent.

Serves a single-page dashboard:
  • Live phone camera (MJPEG from latest.jpg refresh)
  • Phone screen screencap (ADB) when available
  • Printer temps / print progress
  • Film agent + IP cam status

  python3 -m forgeos.vision.hud_server --port 8787
  open http://127.0.0.1:8787/
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MOONRAKER = "http://192.168.1.178:7125"
FILM_DIR = ROOT / "artifacts" / "film_cam"
IPCAM_DIR = ROOT / "artifacts" / "ipcam_agent"
PHONE_URL = "http://192.168.1.250:8080"


def _get_printer() -> Dict[str, Any]:
    try:
        names = [
            "print_stats",
            "extruder",
            "heater_bed",
            "heater_generic heater_bed_outer",
            "gcode_move",
            "virtual_sdcard",
        ]
        q = "&".join(urllib.parse.quote(n, safe="") for n in names)
        with urllib.request.urlopen(MOONRAKER + "/printer/objects/query?" + q, timeout=3) as r:
            return json.loads(r.read().decode())["result"]["status"]
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _refresh_phone_frame() -> None:
    """Background: keep latest.jpg fresh even if agent paused."""
    while True:
        try:
            from forgeos.vision.phone_camera import fetch_jpeg

            FILM_DIR.mkdir(parents=True, exist_ok=True)
            jpeg = fetch_jpeg(PHONE_URL, timeout_s=4, retries=2)
            (FILM_DIR / "latest.jpg").write_bytes(jpeg)
            (IPCAM_DIR / "latest.jpg").write_bytes(jpeg)
        except Exception:
            pass
        time.sleep(0.7)


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ForgeOS Film HUD</title>
<style>
  :root { --bg:#0b0f14; --panel:#141b24; --fg:#e7eef7; --mut:#8aa0b5; --ok:#3ddc97; --bad:#ff5c5c; --acc:#4ea1ff; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--fg); }
  header { display:flex; align-items:center; justify-content:space-between; padding:10px 16px; background:#0e1520; border-bottom:1px solid #1e2a3a; }
  header h1 { font-size:1rem; margin:0; letter-spacing:.04em; }
  .pill { font-size:.75rem; padding:3px 10px; border-radius:999px; background:#1a2736; color:var(--mut); }
  .pill.ok { background:#113325; color:var(--ok); }
  .pill.bad { background:#3a1515; color:var(--bad); }
  main { display:grid; grid-template-columns: 1.4fr 1fr; gap:12px; padding:12px; }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
  .card { background:var(--panel); border:1px solid #1e2a3a; border-radius:12px; overflow:hidden; }
  .card h2 { margin:0; padding:10px 12px; font-size:.85rem; color:var(--mut); border-bottom:1px solid #1e2a3a; text-transform:uppercase; letter-spacing:.06em; }
  .view { position:relative; background:#000; min-height:280px; }
  .view img { width:100%; display:block; background:#000; min-height:240px; object-fit:contain; max-height:52vh; }
  .hud-overlay { position:absolute; left:0; right:0; bottom:0; padding:10px 12px; background:linear-gradient(transparent, rgba(0,0,0,.82)); font-size:.8rem; line-height:1.35; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:12px; }
  .metric { background:#0e1520; border-radius:8px; padding:10px; }
  .metric .k { color:var(--mut); font-size:.7rem; text-transform:uppercase; }
  .metric .v { font-size:1.1rem; margin-top:2px; font-variant-numeric: tabular-nums; }
  pre { margin:0; padding:12px; font-size:.72rem; color:var(--mut); overflow:auto; max-height:220px; }
  .row { display:flex; gap:8px; flex-wrap:wrap; padding:10px 12px; }
  button { background:#1a2e45; color:var(--fg); border:1px solid #2a4060; border-radius:8px; padding:8px 12px; cursor:pointer; font-size:.8rem; }
  button:hover { background:#234060; }
</style>
</head>
<body>
<header>
  <h1>FORGEOS · FILM HUD</h1>
  <div>
    <span id="camPill" class="pill">CAM …</span>
    <span id="adbPill" class="pill">ADB …</span>
    <span id="printPill" class="pill">PRINT …</span>
  </div>
</header>
<main>
  <section class="card">
    <h2>Phone camera (live)</h2>
    <div class="view">
      <img id="cam" src="/cam.jpg?t=0" alt="phone camera"/>
      <div class="hud-overlay" id="camHud">waiting…</div>
    </div>
    <div class="row">
      <button onclick="fetch('/api/action?op=focus')">Focus</button>
      <button onclick="fetch('/api/action?op=torch_on')">Torch ON</button>
      <button onclick="fetch('/api/action?op=torch_off')">Torch OFF</button>
      <button onclick="fetch('/api/action?op=preset_closeup')">Preset closeup</button>
      <button onclick="fetch('/api/action?op=preset_bed')">Preset bed</button>
    </div>
  </section>
  <section class="card">
    <h2>Phone screen (ADB screencap)</h2>
    <div class="view">
      <img id="screen" src="/screen.png?t=0" alt="phone screen"/>
      <div class="hud-overlay">True device screen when ADB paired — else placeholder</div>
    </div>
  </section>
  <section class="card" style="grid-column:1/-1">
    <h2>Printer + agent</h2>
    <div class="grid2" id="metrics"></div>
    <pre id="raw"></pre>
  </section>
</main>
<script>
function pill(id, ok, text) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'pill ' + (ok === true ? 'ok' : ok === false ? 'bad' : '');
}
async function tick() {
  try {
    const r = await fetch('/api/state');
    const s = await r.json();
    const t = Date.now();
    document.getElementById('cam').src = '/cam.jpg?t=' + t;
    document.getElementById('screen').src = '/screen.png?t=' + t;
    const film = s.film || {};
    const stats = (film.stats || {});
    const pr = s.printer || {};
    const ps = pr.print_stats || {};
    const e = pr.extruder || {};
    const b = pr.heater_bed || {};
    const o = pr['heater_generic heater_bed_outer'] || {};
    const vs = pr.virtual_sdcard || {};
    const camOk = !!stats.http_ok || (stats.ok_rate || 0) > 0.5;
    const adbOk = !!(film.adb && film.adb.connected);
    pill('camPill', camOk, camOk ? 'CAM ONLINE' : 'CAM OFFLINE');
    pill('adbPill', adbOk, adbOk ? 'ADB ON' : 'ADB OFF');
    const pstate = (ps.state || '?');
    pill('printPill', pstate === 'printing', 'PRINT ' + pstate);
    document.getElementById('camHud').innerHTML =
      `preset <b>${film.preset||'?'}</b> · ok_rate <b>${((stats.ok_rate||0)*100)|0}%</b> · luma <b>${(stats.last_luma||0).toFixed(0)}</b> · torch <b>${stats.torch?'ON':'off'}</b>`;
    const prog = ((vs.progress||0)*100).toFixed(1);
    document.getElementById('metrics').innerHTML = `
      <div class="metric"><div class="k">Nozzle</div><div class="v">${(e.temperature||0).toFixed(1)} / ${(e.target||0).toFixed(0)}°C</div></div>
      <div class="metric"><div class="k">Bed / Outer</div><div class="v">${(b.temperature||0).toFixed(1)} / ${(o.temperature||0).toFixed(1)}°C</div></div>
      <div class="metric"><div class="k">Progress</div><div class="v">${prog}% · ${ps.filename||'—'}</div></div>
      <div class="metric"><div class="k">Z adjust</div><div class="v">${((pr.gcode_move||{}).homing_origin||[0,0,0])[2]} mm</div></div>
      <div class="metric"><div class="k">Film ticks</div><div class="v">${stats.ticks||0} · fails ${stats.fail||0}</div></div>
      <div class="metric"><div class="k">ADB model</div><div class="v">${(film.adb&&film.adb.model)||'not paired'}</div></div>`;
    document.getElementById('raw').textContent = JSON.stringify({film: film.stats, adb: film.adb, live: s.live}, null, 2);
  } catch (e) {
    pill('camPill', false, 'HUD ERR');
  }
}
setInterval(tick, 700);
tick();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # quiet

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, HTML.encode(), "text/html; charset=utf-8")
            return
        if path == "/cam.jpg":
            for p in (FILM_DIR / "latest.jpg", IPCAM_DIR / "latest.jpg"):
                if p.exists():
                    self._send(200, p.read_bytes(), "image/jpeg")
                    return
            # live fetch
            try:
                from forgeos.vision.phone_camera import fetch_jpeg

                data = fetch_jpeg(PHONE_URL, timeout_s=3, retries=2)
                self._send(200, data, "image/jpeg")
            except Exception as exc:
                self._send(503, str(exc).encode(), "text/plain")
            return
        if path == "/screen.png":
            p = FILM_DIR / "screen.png"
            if p.exists():
                self._send(200, p.read_bytes(), "image/png")
            else:
                # 1x1 transparent-ish placeholder jpeg-as-png skip — plain text
                self._send(200, b"", "image/png")
            return
        if path == "/api/state":
            film = _read_json(FILM_DIR / "hud_state.json")
            if not film:
                film = _read_json(IPCAM_DIR / "status.json")
            live = ""
            for p in (FILM_DIR / "LIVE", IPCAM_DIR / "LIVE"):
                if p.exists():
                    live = p.read_text(encoding="utf-8")
                    break
            payload = {
                "printer": _get_printer(),
                "film": film,
                "live": live,
                "ts": time.time(),
            }
            self._send(200, json.dumps(payload).encode(), "application/json")
            return
        if path.startswith("/api/action"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            op = (qs.get("op") or [""])[0]
            try:
                pc = __import__(
                    "forgeos.vision.phone_control", fromlist=["PhoneControl"]
                ).PhoneControl(PHONE_URL)
                if op == "focus":
                    pc.focus(True)
                elif op == "torch_on":
                    pc.torch(True)
                elif op == "torch_off":
                    pc.torch(False)
                elif op == "preset_closeup":
                    pc.quality(90)
                    pc.focus(True)
                elif op == "preset_bed":
                    pc.optimize_for_bed()
                self._send(200, b'{"ok":true}', "application/json")
            except Exception as exc:
                self._send(500, json.dumps({"ok": False, "err": str(exc)}).encode(), "application/json")
            return
        self._send(404, b"not found", "text/plain")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--no-bg-fetch", action="store_true")
    args = ap.parse_args()
    FILM_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_bg_fetch:
        threading.Thread(target=_refresh_phone_frame, daemon=True).start()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print("ForgeOS Film HUD → http://127.0.0.1:%d/" % args.port, flush=True)
    print("Also on LAN: http://<this-mac-ip>:%d/" % args.port, flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
