# GOD-TIER Vision + ML + Auto-Cal BOM  
## Neptune 4 Pro + ForgeOS + NVIDIA Jetson (from zero)

**Purpose:** Printable shopping list if someone owns **nothing** for the vision stack.  
**Printer stack assumed separate:** N4 Pro + Wham Bam PEX + Brozzl plated copper + Protopasta (already yours).  
**Philosophy:** Multi-view RGB + thermal + Jetson brain; **no LiDAR** (probe does Z better here).

**Currency:** USD ballpark street prices (2025–2026). Verify live SKUs before buy.  
**Lead time:** Prefer Amazon/DigiKey/Mouser/B&H + NVIDIA partners.

---

# QUICK TOTALS

| Tier | What you get | Ballpark |
|---|---|---|
| **Core (must)** | Jetson + power + storage + net + 3× RGB cams + hub + mounts basics | **$900–1,400** |
| **Pro (recommended)** | Core + thermal IR + better hub/cables + UPS + labels | **$1,400–2,200** |
| **God-tier (this list)** | Pro + redundant cams, lighting, thermal upgrade path, tooling, spares | **$2,200–3,500** |

---

# 1. COMPUTE BRAIN (Jetson)

| # | Item | Spec / notes | Example search SKU / class | Qty | Est. $ |
|---|---|---|---|---|---|
| C1 | **NVIDIA Jetson Orin Nano Super 8GB** dev kit *or* partner carrier | 8GB RAM minimum; Super preferred | NVIDIA Orin Nano Super Dev Kit / Seeed / Avalon | 1 | 250–500 |
| C2 | **Carrier board** (if module-only) | Only if not buying full kit | Official / Seeed reComputer | 0–1 | 0–200 |
| C3 | **NVMe SSD** | 256GB min, **1TB recommended** for video datasets | WD SN850X / Samsung 980 1TB M.2 2280 | 1 | 60–120 |
| C4 | **microSD** | 64–128GB JetPack install / recovery | SanDisk Extreme 128GB A2 | 1 | 15–25 |
| C5 | **Jetson power supply** | Official PD or barrel per board docs; **do not underpower** | Kit PSU or 19V/PD 45–65W class | 1 | 25–50 |
| C6 | **Active cooling** | Heatsink + fan if bare module; kit often included | Jetson fan / 4010 5V | 1 | 0–25 |
| C7 | **Case / DIN / desk enclosure** | Ventilated, camera cable access | Jetson case or 3D-printed + acrylic | 1 | 20–60 |
| C8 | **GPIO / expansion header accessories** | Jumpers, standoffs | Assorted M2.5/M3 kit | 1 | 10–20 |

**Subtotal compute:** ~$400–1,000

---

# 2. NETWORKING (Jetson ↔ printer)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| N1 | **Gigabit Ethernet switch** (if needed) | 5–8 port unmanaged | 1 | 15–30 |
| N2 | **Cat6 Ethernet cable** | 1–3 m Jetson→router/switch | 2 | 10–20 |
| N3 | **Spare Cat6** | 5 m | 1 | 8–15 |
| N4 | **USB Ethernet adapter** | Backup if board port dies | 1 | 15–25 |
| N5 | **Wi-Fi antenna set** | Only if board needs external | 0–1 | 0–20 |
| N6 | **Static IP label kit** | Label printer tape or P-touch | 1 | 10–20 |

**Subtotal net:** ~$50–120

---

# 3. CAMERAS — MULTI-VIEW RGB (GOD TIER)

## 3A. Chamber overview (spaghetti / shift / presence)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| V1 | **Chamber USB cam 1080p wide** | UVC, MJPEG/H264, 120°+ FOV, good low light | **2** (primary + spare/rear) | 40–90 each |
| V2 | **Low-light / IR-cut optional cam** | Night LED or starlight for dark enclosure | 1 | 40–80 |
| V3 | **USB extension active** | 3–5 m if cam far from Jetson | 2 | 15–25 each |

*Search class:* “1080p USB webcam wide angle UVC”, Arducam UVC, Logitech C920/C930e (works), industrial UVC modules.

## 3B. Nozzle / toolhead cam (first layer + ooze)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| V4 | **Nozzle camera kit** OR **endoscope 5.5–8 mm USB** | Focusable, 640×480+, 2–5 m cable | **2** (main + spare) | 25–120 each |
| V5 | **Toolhead cam mount** | N4 Pro duct/print mount (Printables/MakerWorld) + hardware | 1–2 | 5–25 |
| V6 | **Cable chain / drag chain** 10×10 or 10×15 | Route USB with X motion | 0.5–1 m | 10–20 |
| V7 | **Strain relief + zip ties + adhesive bases** | Prevent USB yank | 1 kit | 10–15 |
| V8 | **USB-C/A adapters** as needed for endoscope | Match Jetson ports | 3 | 10–15 |

*Search:* “3D printer nozzle camera Klipper”, “5.5mm USB endoscope 2MP”, KB3D/Fabreeko-class if available for your hotend.

## 3C. Oblique first-layer sheet cam (ribs / lift / squish)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| V9 | **Oblique USB 1080p cam** | Fixed focus or manual; 60–90° FOV | 1 | 40–80 |
| V10 | **Articulating arm / gooseneck mount** | Magic arm + clamp | 1 | 20–40 |
| V11 | **Ball head + cold shoe** | Fine aim at bed center | 1 | 15–25 |

## 3D. Optional god-tier extras (RGB)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| V12 | **Global shutter CSI cam** | Less blur on travel (advanced) | 1 | 80–150 |
| V13 | **CSI ribbon set + adapters** | Match Jetson CSI | 1 | 15–30 |
| V14 | **Polarizing filter kit** (clip) | Cut PEX glare | 1–2 | 15–30 |
| V15 | **Macro close-up lenses** for nozzle cam | Detail on bead | 1 | 10–20 |

**Subtotal cameras:** ~$300–700

---

# 4. THERMAL (IR) — heat dissipation / dual-bed soak

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| T1 | **MLX90640 IR array** 32×24 | Breakout + I2C; god-tier *entry thermal* | 1 | 50–80 |
| T2 | **MLX90640 110° FOV** variant | Wider bed coverage | 1 optional | 50–80 |
| T3 | **FLIR Lepton 3.5 + PureThermal breakout** | Higher quality thermal video (upgrade) | 1 | 200–350 |
| T4 | **Qwiic/STEMMA cables** | I2C interconnect | 3 | 10–15 |
| T5 | **Level shifter 3.3V** | If bus needs it | 1 | 5–10 |
| T6 | **IR mount bracket** high rear looking at bed | 3D print + M3 | 1 | 5–15 |
| T7 | **Emissivity calibration targets** (matte tape / black body sticker kit) | PEX calibration | 1 | 10–20 |

**Minimum thermal:** T1 + T4 + T6  
**God-tier thermal:** T1 **and** T3  

**Subtotal thermal:** ~$70–450

---

# 5. USB / POWER DISTRIBUTION (critical — don’t cheap out)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| U1 | **Powered USB3 hub** | 4–7 port, **own 12V/5A PSU**, BC1.2 | **2** (main + spare) | 30–60 each |
| U2 | **Hub power brick spare** | Match hub | 1 | 15–25 |
| U3 | **Short USB3 cables** 0.3–0.5 m | Hub↔Jetson / cams | 6 | 20–40 |
| U4 | **Ferrite cores** clip-on | Noise on long USB | 10 | 10–15 |
| U5 | **USB cable organizer / comb** | | 1 | 10 |
| U6 | **Powered USB isolator** (optional god-tier) | Ground loop killer | 1 | 40–80 |
| U7 | **PoE injector/splitter** (optional) | If mounting Jetson remote | 0–1 | 0–40 |

**Subtotal USB/power dist:** ~$100–250

---

# 6. LIGHTING (vision quality = god-tier)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| L1 | **LED bar 5V/12V neutral white 4000–5000K** | Diffuse, no flicker | 2 | 20–40 |
| L2 | **Diffuser sheet / 3D printed hoods** | Kill specular glare on PEX | 1 kit | 10–20 |
| L3 | **Dimmer / PWM MOSFET module** | Brightness control from Jetson GPIO | 1 | 10–15 |
| L4 | **Ring light small** (optional nozzle area) | Even bead lighting | 1 | 15–25 |
| L5 | **Cable for lights + fuse** | Inline fuse 2A | 1 | 10 |

**Subtotal lighting:** ~$50–100

---

# 7. MOUNTING HARDWARE (printer + desk)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| M1 | **M2/M2.5/M3/M4 screw assortment** | SS button + socket | 1 | 20–30 |
| M2 | **Heat-set inserts M3** | For printed mounts | 50+ | 10–15 |
| M3 | **2020/2040 T-nuts + brackets** (if enclosure) | | 1 kit | 15–25 |
| M4 | **VHB tape + 3M dual lock** | Temporary cam aim | 1 | 15–20 |
| M5 | **Magic arms / goosenecks** | Oblique + chamber | 2 | 30–50 |
| M6 | **Super clamps** | Desk/frame | 2 | 15–25 |
| M7 | **PETG/ABS filament for mounts** | High-temp mounts near bed | 1 kg | 20–30 |
| M8 | **Standoffs nylon/brass kit** | Jetson board | 1 | 10 |
| M9 | **Cable chain mounts** printed | N4 Pro specific | 1 set | 5–15 |
| M10 | **Anti-vibration foam feet** | Jetson case | 1 | 8–12 |

**Subtotal mounts:** ~$150–250

---

# 8. POWER PROTECTION / SHOP SAFETY

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| P1 | **UPS 600–1000VA** | Jetson + hub + switch (not whole printer heater) | 1 | 80–150 |
| P2 | **Smart power strip** | Metered / surge | 1 | 25–40 |
| P3 | **Dedicated surge protector** | Printer already; add for vision desk | 1 | 20–30 |
| P4 | **Fire extinguisher CO2/ABC** small | Shop safety | 1 | 30–50 |
| P5 | **Smoke detector near print cell** | | 1 | 15–30 |
| P6 | **E-stop mushroom** (optional wired later) | Secondary stop culture | 1 | 15–25 |

**Subtotal safety/power:** ~$180–320

---

# 9. WORKSTATION / FLASH / DEBUG (if starting from zero)

| # | Item | Spec | Qty | Est. $ |
|---|---|---|---|---|
| W1 | **USB keyboard + mouse** | Jetson setup | 1 | 20–40 |
| W2 | **HDMI cable + monitor** (or use SSH-only) | First boot | 1 | 0–100 |
| W3 | **Laptop already owned** | SSH + VS Code | 0 | 0 |
| W4 | **USB-C / USB-A data cables** | Flash / serial | 3 | 15–25 |
| W5 | **USB serial console cable 3.3V** | Debug | 1 | 10–15 |
| W6 | **SD card reader** | | 1 | 10–15 |
| W7 | **Digital multimeter** | Continuity / 5V rails | 1 | 20–40 |
| W8 | **ESD strap** | | 1 | 8–12 |
| W9 | **Precision screwdriver set** | | 1 | 15–30 |
| W10 | **Flush cutters + wire strippers** | | 1 | 15–25 |
| W11 | **Helping hands / third hand** | | 1 | 10–20 |
| W12 | **Isopropyl alcohol 99% + wipes** | Lens + PEX clean | 1 | 10–15 |
| W13 | **Compressed air / blower** | Dust on sensors | 1 | 10–20 |
| W14 | **Label maker** | Cable IDs | 1 | 20–40 |
| W15 | **Notebook / print this BOM** | | 1 | 5 |

**Subtotal tools/debug:** ~$150–350 (less if you already have tools)

---

# 10. SOFTWARE / ACCOUNTS (free–cheap)

| # | Item | Notes | Est. $ |
|---|---|---|---|
| S1 | JetPack SDK | NVIDIA | 0 |
| S2 | Docker (optional) | Model serving | 0 |
| S3 | PyTorch / TensorRT / OpenCV | Jetson packages | 0 |
| S4 | ForgeOS repo | This project | 0 |
| S5 | Moonraker already on printer | | 0 |
| S6 | Optional cloud backup SSD | Offsite dataset | 0–50/yr |

---

# 11. SPARES (god-tier always buys spares)

| # | Item | Qty | Est. $ |
|---|---|---|---|
| X1 | Spare USB cam (chamber class) | 1 | 40–80 |
| X2 | Spare endoscope / nozzle cam | 1 | 25–60 |
| X3 | Spare powered hub | 1 | 30–50 |
| X4 | Spare NVMe (clone image) | 1 | 60–100 |
| X5 | Spare microSD with golden JetPack image | 1 | 15–25 |
| X6 | Extra USB cables (assorted) | 5 | 20 |
| X7 | Extra M3 screws/inserts | 1 bag | 10 |
| X8 | Silicone sock / spare nozzle (printer) | 1–2 | 15–30 |

**Subtotal spares:** ~$200–350

---

# 12. OPTIONAL ADVANCED (only after Core works)

| # | Item | Why | Est. $ |
|---|---|---|---|
| A1 | Second Jetson | Multi-printer | 250+ |
| A2 | PoE cameras | Long cable runs | 100–200 each |
| A3 | Machine vision global shutter set | High-speed bead analysis | 150–400 |
| A4 | Stereo pair + baseline bar | 3D first-layer height research | 100–250 |
| A5 | **LiDAR** | **Skip for N4 Pro v1** | — |
| A6 | GigE industrial cam | Overkill unless productizing | 300+ |

---

# 13. MASTER CHECKLIST (print & tick)

## Compute
- [ ] C1 Jetson Orin Nano Super 8GB  
- [ ] C3 NVMe 1TB  
- [ ] C4 microSD 128GB  
- [ ] C5 Official/high-quality PSU  
- [ ] C6 Cooling  
- [ ] C7 Case  

## Network
- [ ] N1 Switch (if needed)  
- [ ] N2–N3 Ethernet cables  
- [ ] Static IP plan for Jetson  

## Cameras
- [ ] V1 Chamber ×2  
- [ ] V4 Nozzle cam ×2  
- [ ] V9 Oblique cam  
- [ ] V6 Cable chain  
- [ ] V10–V11 Mounts  

## Thermal
- [ ] T1 MLX90640  
- [ ] T3 FLIR Lepton (god-tier)  
- [ ] T4–T6 Cables + mount  

## USB / power
- [ ] U1 Powered USB3 hub ×2  
- [ ] U3 Short USB3 cables  
- [ ] U4 Ferrites  

## Lighting
- [ ] L1 LED bars ×2  
- [ ] L2 Diffusers  
- [ ] L3 Dimmer  

## Mounts / tools / safety
- [ ] M1–M10 hardware  
- [ ] P1 UPS  
- [ ] P4–P5 Fire/smoke  
- [ ] W1–W15 tools (as needed)  

## Spares
- [ ] X1–X8  

---

# 14. RECOMMENDED BUY ORDER (don’t order random)

1. **Jetson + PSU + NVMe + SD + Ethernet** (get SSH working)  
2. **Powered USB3 hub + 1 chamber cam** (V0 stills)  
3. **Nozzle cam + cable chain** (first-layer AI)  
4. **Oblique cam + lighting** (ribs/lift)  
5. **MLX90640 thermal** (soak gate)  
6. **Spares + UPS + Lepton upgrade**  
7. **Never buy LiDAR first**  

---

# 15. WIRING CHEAT SHEET

```text
Wall → UPS → Smart strip
              ├─ Jetson PSU
              ├─ USB3 hub PSU
              ├─ LED PSU / 12V brick
              └─ (Printer on OWN surge — heaters not on small UPS)

Jetson eth ──→ LAN ──→ Printer 192.168.1.178

Jetson USB ──→ Hub ──┬─ cam_chamber
                     ├─ cam_nozzle (via chain to toolhead)
                     ├─ cam_oblique
                     └─ (thermal USB if Lepton PureThermal)

Jetson I2C ──→ MLX90640 (ir_bed)
```

---

# 16. CONFIG NAMES (match software)

| Hardware | `vision_rig.yaml` key |
|---|---|
| Chamber | `cam_chamber` |
| Nozzle | `cam_nozzle` |
| Oblique | `cam_oblique` |
| Bed IR | `ir_bed` |
| Hotend IR | `ir_hotend` |

Software: `configs/vision_rig.yaml`, service `forgeos.vision.service`.

---

# 17. ESTIMATED GRAND TOTAL (GOD TIER, from nothing)

| Block | Range |
|---|---|
| Compute | $400–1,000 |
| Network | $50–120 |
| Cameras | $300–700 |
| Thermal | $70–450 |
| USB/power | $100–250 |
| Lighting | $50–100 |
| Mounts | $150–250 |
| Safety/UPS | $180–320 |
| Tools (if none) | $150–350 |
| Spares | $200–350 |
| **TOTAL** | **~$1,650–3,900** |

**Practical “buy this month” cart (~$1,200–1,800):**  
C1+C3+C4+C5 + U1 + V1 + V4 + V9 + V6 + L1 + M1/M5 + T1 + N2 + P1.

---

# 18. PRINTER-SIDE (you mostly have — listed for completeness)

| Item | Status |
|---|---|
| Elegoo Neptune 4 Pro | Owned |
| Wham Bam PEX sheet | Owned |
| Brozzl plated copper 0.4 | Owned |
| Protopasta HTPLA | Owned |
| Ethernet to LAN | Owned |
| Klipper/Moonraker/ForgeOS | Owned |
| Hardened nozzle (for CF later) | Optional buy |
| ADXL for shaper | Optional buy |

---

*BOM v1 — ForgeOS god-tier vision rig. Update prices at purchase time. No LiDAR in v1.*
