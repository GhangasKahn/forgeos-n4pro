# ForgeOS Vision + ML + Auto-Calibration Stack

**Goal:** Multi-view sensing + on-device ML on an **NVIDIA Jetson**, talking to the **Neptune 4 Pro (Klipper/Moonraker)** so calibration and process control close the loop (first layer, bed heat, motion, failures) without babysitting.

**Printer today:** `mks@192.168.1.178` — weak 1 GB board → **all vision/ML lives on Jetson**, not on the printer SBC.

---

## 1. Roles: who thinks, who moves

```text
┌─────────────────────────────────────────────────────────────┐
│  NVIDIA Jetson (Orin Nano Super class)                      │
│  - multi-camera capture                                      │
│  - IR thermal frames                                         │
│  - ML inference (first layer, spaghetti, thermal map)        │
│  - calibration state machine                                 │
│  - MQTT / HTTP client → Moonraker                            │
└──────────────────────────┬──────────────────────────────────┘
                           │ Ethernet LAN
                           │ Moonraker :7125 (gcode, status, mesh)
┌──────────────────────────▼──────────────────────────────────┐
│  Neptune 4 Pro (znp-k1)                                      │
│  - Klipper real-time motion / heaters / probe                │
│  - ForgeOS macros (Z, retract, env)                          │
│  - NO heavy ML                                               │
└─────────────────────────────────────────────────────────────┘
```

**Law:** Jetson may *request* moves/temps; **Klipper remains the only safety authority** (thermal runaway, endstops, estop).

---

## 2. What each sensor is actually good for

| Sensor | Captures | Use for auto-cal / control | Priority |
|---|---|---|---|
| **RGB chamber (wide)** | Whole bed + part silhouette | Spaghetti, layer shift, missing part, print progress | **P0** |
| **RGB toolhead / nozzle cam** | Nozzle tip + fresh bead | First-layer AI: under/over extrude, gaps, ribs, scrape | **P0** |
| **RGB side / oblique** | 30–45° view of first layer sheet | Squish / ribbing / lift (your current pain) | **P1** |
| **Thermal IR (array or module)** | Bed + nozzle heat field | Dual-bed soak quality, cold corners, heat dissipation, failed heater | **P1** |
| **Optional 2nd chamber** rear/side | Occlusion-free view | Multi-view fusion when front cam blocked | **P2** |
| **Structured light / stereo** | Dense 3D surface | Research bed flatness / first-layer height map | **P3** |
| **LiDAR (Bambu-style)** | Sparse Z / surface | **Skip for N4 Pro** — closed systems; your inductive probe + mesh already do mechanical Z better and cheaper | **Not recommended** |
| **ToF single-point** | Cheap distance | Weak for PEI/PEX shiny surfaces; optional experiment only | **P3** |
| **ADXL (existing path)** | Vibration | Input shaper / resonance (not vision, but same Jetson can log) | **P1** |

**Bottom line buy list (proficient, not sci-fi):**

1. 1× nozzle cam (endoscope or KB3D/Fabreeko-style nozzle cam)  
2. 1× chamber USB cam (1080p, wide, good low light)  
3. 1× oblique USB cam (first-layer sheet)  
4. 1× thermal: **MLX90640** (cheap grid) *or* **FLIR Lepton** (better image)  
5. **No LiDAR** for v1  

---

## 3. Compute: “Nano Super”

Use a current **Jetson Orin Nano Super** (or Orin Nano 8 GB if Super unavailable)—not the original 2019 Nano if you want multi-cam + modern models.

| Need | Spec |
|---|---|
| RAM | **8 GB** minimum for multi-stream + YOLO-class models |
| Storage | 256 GB+ NVMe/SSD |
| Power | Official PD / barrel supply (cams + Jetson) |
| Network | **Ethernet** to same LAN as printer (Wi‑Fi OK as backup) |
| Cameras | Prefer **USB3** hub (powered) for flexibility on N4 Pro; CSI for 1–2 fixed cams if mounts allow |
| OS | JetPack 6.x |

**Why not printer-only:** N4 Pro board is already at ~1 GB RAM / eMMC full; multi-view ML will kill it.

---

## 4. Multi-view capture plan

### Views

| ID | Name | Mount | FOV target | Rate | Primary models |
|---|---|---|---|---|---|
| `cam_chamber` | Overview | Frame / enclosure corner | Full 225 mm bed | 5–10 fps | spaghetti, presence, shift |
| `cam_nozzle` | Nozzle | Toolhead / duct | Nozzle + ~20 mm bead | 10–15 fps | first layer, ooze whisker |
| `cam_oblique` | Sheet | Front bar, 35° down | Center 80–120 mm of bed | 5–10 fps | ribbing, adhesion, lift |
| `ir_bed` | Thermal bed | Above bed or side high | Full plate | 1–4 fps | soak uniformity, gradients |
| `ir_hotend` | Thermal hotend | Optional near carriage | Block/nozzle region | 1–2 fps | heat soak, clog risk |

### Capture modes (automation)

| Mode | When | What is recorded |
|---|---|---|
| `IDLE_SNAPSHOT` | Every N min | Chamber + IR stills for drift |
| `HEAT_SOAK` | Dual-bed heat | IR sequence → uniformity score |
| `MESH_WATCH` | During bed mesh | Chamber motion blur / head track |
| `FIRST_LAYER` | Z-tune / print L0 | Nozzle + oblique bursts |
| `LAYER_AUDIT` | Every K layers | Chamber frame + optional nozzle |
| `FAULT_BURST` | On anomaly | All cams 3–5 s ring buffer dump |

---

## 5. ML modules (Jetson)

| Module | Input | Output | Action via Moonraker |
|---|---|---|---|
| **FirstLayerScorer** | nozzle + oblique RGB | score 0–1, labels: good / high_z / low_z / under / over / ribs / lift | `FORGE_BABY_UP/DOWN`, pause, flow nudge |
| **SpaghettiDetector** | chamber | spaghetti probability | pause / cancel |
| **ThermalMapAnalyzer** | IR bed | peak-to-peak °C, cold corner ID | extend soak, warn outer zone |
| **BedMotionObserver** | chamber + toolhead telemetry | residual motion / layer shift | pause |
| **OozeWhisker** | nozzle cam idle | whisker present | tip clean / temp −2 °C |
| **CalibPolicy** (classical + light ML) | scores + probe mesh | next Z/flow/temp/retract trial | journal + apply if armed |

**Training strategy (honest):**

- v1: **classical CV + small pretrained nets** (YOLO-nano / MobileNet features) fine-tuned on *your* PEX + HTPLA images  
- v2: active learning — every pause/manual label goes into dataset on Jetson SSD  
- Do **not** train huge models on Jetson; train on Mac/desktop, deploy TensorRT/ONNX to Jetson  

---

## 6. How Jetson ↔ printer talk

### Primary: Moonraker HTTP + WebSocket

| Direction | API |
|---|---|
| Jetson → Printer | `POST /printer/gcode/script` (macros, baby Z, pause) |
| Jetson → Printer | `POST /printer/print/start|cancel|pause` |
| Printer → Jetson | `WS /websocket` subscribe `notify_status_update` (temps, print_stats, toolhead) |
| Both | Job hooks: on `printing` enter `FIRST_LAYER` mode |

### Optional: MQTT bus (nice for multi-service)

```text
forgeos/printer/status     # mirrored telemetry
forgeos/vision/events      # {type, severity, scores, ts}
forgeos/vision/commands    # human or policy commands
forgeos/calib/state        # calibration FSM state
```

### Zero-trust (same as ForgeOS)

- Vision may **suggest**; apply only if `FORGE_ARM` / vision-arm token set  
- Hard envelopes still clamp Z steps (0.02 mm), temps, flow  

---

## 7. What you can automate (mapped to sensors)

| Phenomenon | Sensors | Automation |
|---|---|---|
| Z too low (empty bed / scrape) | nozzle + oblique | detect bare PEI + no bead → `BABY_UP` |
| Z too high / ribs | oblique texture + nozzle width | score ribs → `BABY_DOWN` + flow bump |
| Dual-bed soak incomplete | IR bed | wait until ΔT across plate &lt; threshold |
| Outer zone cold | IR | longer soak / warn |
| Stringing / whisker | nozzle cam | retract profile bump, tip clean |
| Spaghetti / fail | chamber | pause + snapshot |
| Layer shift | chamber + steppers | pause |
| Heat dissipation / cool rate | IR time series | AFTER cool policy |
| Bed flex / slap (Wham Bam) | chamber motion + optional accel | detect plate not seated |

---

## 8. Wiring sketch (shop)

```text
[USB3 powered hub]──┬── chamber cam
                    ├── oblique cam
                    └── nozzle cam (USB endoscope) ── toolhead cable strain relief

[Jetson Orin Nano Super]
   eth0 ──── LAN ──── Printer eth0 (192.168.1.178)
   USB  ──── hub
   CSI0 ──── (optional) fixed chamber cam
   I2C/SPI ─ MLX90640 thermal (or USB thermal)

Power: Jetson brick + hub supply separate from printer PSU.
Ground: keep USB grounds clean; ferrite on long USB runs.
```

**Mount notes (N4 Pro):**

- Nozzle cam: front of toolhead, angled at extrusion point; PTFE/cable chain for USB  
- Oblique: front gantry or enclosure crossbar  
- Chamber: rear-left high  
- IR: high rear looking down (not through glass if emissivity wrong—calibrate)  

---

## 9. Software layout (repo)

```text
forgeos/
  vision/
    __init__.py
    bus.py              # Moonraker WS + optional MQTT
    capture.py          # multi-cam + IR frame grab
    events.py           # event schema
    scorers/
      first_layer.py
      thermal_map.py
      spaghetti.py
    calib/
      fsm.py            # auto Z / soak / flow calibration state machine
    service.py          # main loop on Jetson
deployment/
  jetson/
    forgeos-vision.service
    install_jetson.sh
configs/
  vision_rig.yaml       # camera device paths, rates, arms
```

---

## 10. Phased build (implementable)

### Phase V0 — talk only (this week)
- Jetson on LAN  
- Service polls Moonraker + can run `FORGE_Z_STATUS`  
- Save stills from 1 USB cam timed to print events  

### Phase V1 — dual RGB + first layer score
- Chamber + nozzle (or oblique)  
- Classical “bead vs bare bed” + simple CNN  
- Semi-auto: **suggest** BABY_UP/DOWN; operator confirms  

### Phase V2 — closed-loop Z-tune
- Armed mode: auto babystep within ±0.15 mm envelope during Z-tune square  
- Journal images + Z + score  

### Phase V3 — thermal soak gate
- MLX90640 / Lepton  
- `FORGE_HEAT_DUAL_BED` waits on **vision thermal uniformity**, not only single thermistors  

### Phase V4 — full print guardian
- Spaghetti + layer audit + auto pause  
- Dataset export for fine-tuning  

---

## 11. Shopping list (concrete tiers)

### Tier A — start strong (~$400–700 sensors + mounts, excl. Jetson)

| Item | Example class |
|---|---|
| Jetson Orin Nano Super 8 GB | NVIDIA dev kit / partner board |
| USB3 powered hub | 4-port industrial |
| Chamber cam | 1080p UVC wide (e.g. good Logitech / Arducam UVC) |
| Nozzle cam | 5.5–8 mm endoscope or printer nozzle cam kit |
| Oblique cam | second 1080p UVC |
| Thermal | MLX90640 32×24 breakout **or** FLIR Lepton breakout |
| Cable chain / mounts | N4 Pro toolhead + frame prints |

### Tier B — later

| Item | Why |
|---|---|
| Better thermal (Lepton 3.5) | Heat dissipation maps |
| CSI global shutter cam | Less motion blur on travel |
| Second Jetson only if multi-printer |

### Skip for now

- Full LiDAR turret  
- Multi-stereo photogrammetry rig  
- Running YOLO on printer SBC  

---

## 12. Safety & privacy

- Estop remains physical + Mainsail  
- Vision arm separate from print arm  
- Store images locally on Jetson SSD; retention policy (e.g. 14 days)  
- IR is heat, not “see through walls” fantasy—emissivity of PEX/PEI must be calibrated  

---

## 13. Success metrics

| Metric | Target |
|---|---|
| Auto Z-tune converges | ≤ 6 babysteps to “good” score ≥ 0.85 |
| False pause rate | &lt; 5% on known-good prints |
| Thermal soak gate | detects cold outer zone before first layer |
| Ribbing classification | agrees with human on 20 labeled coupons |

---

*This is the map. Next implementation step: V0 Jetson bridge service in `forgeos/vision/` + `vision_rig.yaml` skeleton.*
