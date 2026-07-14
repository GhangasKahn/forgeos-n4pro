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
SWARM_DIR = ROOT / "artifacts" / "film_swarm"
PHONE_URL = "http://192.168.1.250:8080"

# Full-screen agent HUD for the phone (open via ADB browser)
PHONE_AGENTS_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"/>
<meta name="mobile-web-app-capable" content="yes"/>
<title>ForgeOS AGENTS LIVE</title>
<style>
  :root { --bg:#05080c; --fg:#e8f1ff; --mut:#7f96ad; --ok:#2dff9a; --bad:#ff4d6d; --line:#1b2a3d; --card:#0d1520; }
  * { box-sizing: border-box; }
  html, body { margin:0; background:var(--bg); color:var(--fg); font-family: ui-sans-serif, system-ui, sans-serif; }
  header { position:sticky; top:0; z-index:5; background:rgba(5,8,12,.92); border-bottom:1px solid var(--line);
    padding:10px 12px; display:flex; justify-content:space-between; align-items:center; backdrop-filter: blur(8px); }
  header h1 { font-size:14px; margin:0; letter-spacing:.12em; }
  .clk { font-variant-numeric: tabular-nums; color:var(--mut); font-size:12px; }
  .banner { padding:8px 12px; font-size:12px; border-bottom:1px solid var(--line); color:var(--mut); }
  .banner b { color:var(--ok); }
  .agents { padding:10px; display:flex; flex-direction:column; gap:8px; }
  .agent { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px; display:grid;
    grid-template-columns: 12px 1fr auto; gap:10px; align-items:center; }
  .dot { width:12px; height:12px; border-radius:50%; background:#445; box-shadow:0 0 0 0 rgba(45,255,154,.4); }
  .dot.on { background:var(--ok); animation: pulse 1.4s infinite; }
  .dot.off { background:var(--bad); }
  @keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(45,255,154,.55);} 70%{box-shadow:0 0 0 10px rgba(45,255,154,0);} 100%{box-shadow:0 0 0 0 rgba(45,255,154,0);} }
  .name { font-weight:700; font-size:15px; text-transform:uppercase; letter-spacing:.06em; }
  .role { color:var(--mut); font-size:11px; margin-top:2px; }
  .badge { font-size:11px; padding:4px 8px; border-radius:999px; background:#132033; color:var(--mut); }
  .badge.live { color:var(--ok); background:#0d2a1c; }
  .metrics { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:0 10px 10px; }
  .m { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; }
  .m .k { font-size:10px; color:var(--mut); text-transform:uppercase; }
  .m .v { font-size:16px; margin-top:3px; font-variant-numeric:tabular-nums; }
  .feed { padding:0 10px 10px; }
  .feed img { width:100%; border-radius:12px; border:1px solid var(--line); background:#000; max-height:28vh; object-fit:cover; }
  .log { margin:0 10px 20px; padding:10px; background:#070c12; border:1px solid var(--line); border-radius:10px;
    font-size:10px; color:var(--mut); max-height:22vh; overflow:auto; white-space:pre-wrap; font-family: ui-monospace, monospace; }
</style>
</head>
<body>
<header>
  <h1>FORGEOS · AGENTS IRT</h1>
  <div class="clk" id="clk">--:--:--</div>
</header>
<div class="banner" id="banner">booting swarm link…</div>
<div class="feed"><img id="cam" src="/cam.jpg?t=0" alt="cam"/></div>
<div class="metrics" id="metrics"></div>
<div class="agents" id="agents"></div>
<pre class="log" id="log">waiting for bus…</pre>
<script>
const ROLES = {
  director: 'Shot plan · closeups · cues',
  capture: 'Frames · bursts · latest.jpg',
  optics: 'Focus · torch · quality',
  adb: 'Wake · launch cam · screencap',
  printer: 'Print events · milestones',
  archive: 'Session footage archive',
  comms: 'Bus aggregator · HUD state',
  adaptive: 'Bed/nozzle process brain',
  hud: 'This dashboard'
};
function fmt(ts){ return new Date().toLocaleTimeString(); }
async function tick(){
  document.getElementById('clk').textContent = fmt();
  try {
    const r = await fetch('/api/state?phone=1');
    const s = await r.json();
    document.getElementById('cam').src = '/cam.jpg?t=' + Date.now();
    const swarm = s.swarm || {};
    const recent = (swarm.recent || s.recent || []).slice().reverse();
    const agentsSeen = {};
    (recent||[]).forEach(m => {
      if (m.sender) agentsSeen[m.sender] = m;
      if (m.topic && m.topic.startsWith('swarm.agent')) {
        const a = (m.payload||{}).agent || m.sender;
        agentsSeen[a] = m;
      }
    });
    // known roster always shown
    const roster = ['director','capture','optics','adb','printer','archive','comms'];
    const live = (s.live||'') + ' ' + (s.swarm_live||'');
    const camOn = /ONLINE|CAPTURE ONLINE|http=True/i.test(live) || (s.film && s.film.stats && s.film.stats.http_ok);
    const pr = s.printer || {};
    const ps = pr.print_stats || {};
    const e = pr.extruder || {};
    const b = pr.heater_bed || {};
    document.getElementById('banner').innerHTML =
      `CAM <b>${camOn?'ONLINE':'OFFLINE'}</b> · PRINT <b>${ps.state||'?'}</b> · SWARM <b>${s.swarm_up?'ACTIVE':'…'}</b> · Z <b>${((pr.gcode_move||{}).homing_origin||[0,0,'?'])[2]}</b>`;
    document.getElementById('metrics').innerHTML = `
      <div class="m"><div class="k">Nozzle</div><div class="v">${(e.temperature||0).toFixed(0)}° / ${(e.target||0).toFixed(0)}°</div></div>
      <div class="m"><div class="k">Bed</div><div class="v">${(b.temperature||0).toFixed(0)}°</div></div>
      <div class="m"><div class="k">Progress</div><div class="v">${(((pr.virtual_sdcard||{}).progress||0)*100).toFixed(0)}%</div></div>
      <div class="m"><div class="k">Bus msgs</div><div class="v">${(recent||[]).length}</div></div>`;
    const now = Date.now()/1000;
    document.getElementById('agents').innerHTML = roster.map(name => {
      const m = agentsSeen[name];
      const age = m ? (now - (m.ts||0)) : 999;
      const on = age < 15;
      const last = m ? (m.topic || '') : 'waiting';
      return `<div class="agent">
        <div class="dot ${on?'on':'off'}"></div>
        <div><div class="name">${name}</div><div class="role">${ROLES[name]||''}<br/><span style="opacity:.7">${last}</span></div></div>
        <div class="badge ${on?'live':''}">${on?'LIVE':'—'} ${on?Math.max(0,age|0)+'s':''}</div>
      </div>`;
    }).join('');
    document.getElementById('log').textContent = (recent||[]).slice(0,18).map(m =>
      `${new Date((m.ts||0)*1000).toLocaleTimeString()}  ${m.sender} → ${m.topic}`
    ).join('\n') || 'no messages yet — start swarm';
  } catch(e) {
    document.getElementById('banner').innerHTML = 'HUD link error — is Mac server up?';
  }
}
setInterval(tick, 600);
tick();
// keep screen suggestion
try { screen.orientation && screen.orientation.lock('portrait'); } catch(e){}
</script>
</body>
</html>
"""


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
        if path in ("/agents", "/phone", "/phone-hud", "/irt"):
            self._send(200, PHONE_AGENTS_HTML.encode(), "text/html; charset=utf-8")
            return
        if path == "/cam.jpg":
            for p in (
                SWARM_DIR / "latest.jpg",
                FILM_DIR / "latest.jpg",
                IPCAM_DIR / "latest.jpg",
                SWARM_DIR / "frames" / "latest.jpg",
            ):
                if p.exists() and p.stat().st_size > 500:
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
            swarm = _read_json(SWARM_DIR / "swarm_state.json")
            live = ""
            for p in (SWARM_DIR / "LIVE", FILM_DIR / "LIVE", IPCAM_DIR / "LIVE"):
                if p.exists():
                    live = p.read_text(encoding="utf-8")
                    break
            swarm_live = ""
            if (SWARM_DIR / "SWARM_LIVE").exists():
                swarm_live = (SWARM_DIR / "SWARM_LIVE").read_text(encoding="utf-8")
            payload = {
                "printer": _get_printer(),
                "film": film,
                "swarm": swarm,
                "recent": (swarm.get("recent") if isinstance(swarm, dict) else None) or [],
                "live": live,
                "swarm_live": swarm_live,
                "swarm_up": bool(swarm_live) or bool(swarm.get("recent")),
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
