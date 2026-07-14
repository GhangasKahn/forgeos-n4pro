# ADB full phone control + Film Cam agent + live HUD

## Architecture

```
Nothing Phone
  ├─ Wireless ADB  ──► AdbPhone (launch IP Webcam, keep awake, screencap, keys)
  └─ IP Webcam :8080 ──► HTTP cam (shot.jpg, torch, focus, quality)
              │
              ▼
     FilmCamAgent  (film presets + continuous grab)
              │
              ▼
     HUD server :8787  (browser dashboard)
              │
              ▼
     Moonraker printer overlay
```

## 1. One-time ADB pair (required for FULL control)

On the phone:
1. **Settings → About phone** → tap **Build number** 7×  
2. **Settings → System → Developer options**  
3. Enable **Wireless debugging**  
4. Tap **Wireless debugging** → **Pair device with pairing code**  
5. Note **IP:port** (pairing port, not 8080) and **6-digit code**

On the Mac:

```bash
export PATH="$HOME/.local/platform-tools:$PATH"
adb pair 192.168.1.250:XXXXX
# enter the 6-digit code when asked

# Then connect (use the "IP address & port" shown on Wireless debugging main screen)
adb connect 192.168.1.250:YYYYY
adb devices
```

Leave **Wireless debugging ON**. IP Webcam can still run in parallel.

## 2. Film Cam agent (camera + film optimization)

```bash
python3 -m forgeos.vision.film_cam_agent --ip 192.168.1.250 --preset printer_bed -v

# after ADB paired:
python3 -m forgeos.vision.film_cam_agent --ip 192.168.1.250 --adb-serial 192.168.1.250:YYYYY --preset closeup -v
```

Presets: `printer_bed` | `closeup` | `wide_chamber`

Outputs in `artifacts/film_cam/`:
- `latest.jpg` — live camera  
- `screen.png` — phone screen (ADB)  
- `hud_state.json` / `LIVE`

## 3. Real-time HUD

```bash
python3 -m forgeos.vision.hud_server --port 8787
open http://127.0.0.1:8787/
```

HUD shows:
- Live phone camera feed  
- Phone screen (when ADB connected)  
- Printer nozzle/bed/progress/Z  
- Focus / torch buttons  
- Agent stats  

## 4. What full ADB unlocks

| Capability | HTTP IP Webcam only | + ADB |
|------------|---------------------|-------|
| Snapshots / stream | Yes | Yes |
| Torch / focus / quality | Yes | Yes |
| Auto-launch IP Webcam | No | **Yes** |
| Keep screen on | Partial | **Yes** |
| Wake phone | No | **Yes** |
| See real phone UI | No | **Screencap HUD** |
| Tap Start server | Manual | **Can automate** |

## Security

ADB on LAN is powerful — only on trusted home Wi‑Fi. Don’t expose ports to the internet.
