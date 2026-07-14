# Use Nothing Phone 4a Pro as ForgeOS eyes (temporary)

No Jetson required. Phone streams over Wi‑Fi; Mac runs the vision loop.

## 1. Phone setup (2 minutes)

1. Install **[IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)** (Android — works on Nothing OS).
2. Connect phone to the **same Wi‑Fi** as your Mac / printer (`192.168.1.x`). Turn **off VPN / mobile data preference** for this.
3. Open **IP Webcam** → scroll to bottom → **Start server**.
4. Note the URL on screen, e.g. `http://192.168.1.42:8080`.
5. On the Mac browser, open that URL — you should see the camera page.
6. Mount the phone:
   - **Best for first layer:** angled ~30–45° looking at the bed center / nozzle path (like “oblique”).
   - Clip to enclosure, tripod, or stack of filament boxes. Keep it still.
   - Disable auto-lock / keep screen on while streaming (IP Webcam usually keeps CPU awake).

Optional IP Webcam settings:
- Resolution 1280×720 or 640×480 (lower = faster)
- Quality medium
- Port **8080**

## 2. Test link

```bash
cd ~/forgeos-n4pro
python3 scripts/phone_cam_test.py http://PHONE_IP:8080
```

Success saves `artifacts/phone_cam/phone_test.jpg` and prints a first-layer score.

If it fails:
- Phone and Mac not on same subnet
- Server not started
- Firewall / Private Wi‑Fi address on iOS (N/A — you're on Android)
- Need `pip install pillow` for pixel scoring (still can fetch JPEG without it)

```bash
pip install pillow   # recommended on Mac for real row/flat scores
```

## 3. Run vision with phone eyes

```bash
python3 -m forgeos.vision.service \
  --moonraker http://192.168.1.178:7125 \
  --phone-url http://PHONE_IP:8080 \
  --interval 0.5 \
  -v
```

Or put the URL in `configs/vision_rig.yaml`:

```yaml
phone_camera:
  url: "http://192.168.1.42:8080"
```

## 4. What I can “see” with this

| Available now | Not yet (needs multi-cam / thermal) |
|---------------|--------------------------------------|
| Bed presence / empty vs plastic (coverage) | Nozzle-only macro focus |
| Rib / texture proxy (row variance) | True IR bed map |
| Live scores into adaptive controller | Stereo / multi-view |
| Snapshots in `artifacts/phone_cam/` | Auto spaghetti CNN |

Suggest-only by default. Add `--arm` only after you trust scores.

## 5. Dual use with zero-vision brain

Keep process brain for bed/nozzle:

```bash
python3 -m forgeos.adaptive.service --interval 0.5
```

And phone vision for optical first-layer:

```bash
python3 -m forgeos.vision.service --phone-url http://PHONE_IP:8080 --interval 0.5
```

Both talk to the same Moonraker; vision stays suggest-only until armed.

## Security note

IP Webcam is **unencrypted HTTP on your LAN**. Fine at home; don’t port-forward it to the internet.
