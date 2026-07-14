"""Phone-as-camera capture (Android IP Webcam / similar) — zero Jetson required.

Recommended app: **IP Webcam** (Pavel Khlebovich) on Nothing Phone 4a Pro.
  1) Phone + Mac/printer on same Wi‑Fi (192.168.1.x)
  2) Open IP Webcam → Start server
  3) Note URL e.g. http://192.168.1.42:8080
  4) Run: python3 -m forgeos.vision.service --phone-url http://192.168.1.42:8080

Endpoints tried (in order):
  /shot.jpg          — single JPEG (IP Webcam)
  /photo.jpg         — alternate
  /video             — MJPEG stream (first frame)
  raw URL            — if you pass a direct image URL
"""

from __future__ import annotations

import logging
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from forgeos.vision.scorers.first_layer import FirstLayerResult, score_from_gray_rows

log = logging.getLogger("forgeos.vision.phone")


@dataclass
class PhoneFrame:
    jpeg: bytes
    width: int
    height: int
    gray_rows: List[float]  # mean luma per image row (downsampled)
    coverage: float
    ts: float


def _http_get(url: str, timeout_s: float = 3.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ForgeOS-PhoneCam/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def fetch_jpeg(
    base_url: str,
    timeout_s: float = 5.0,
    *,
    retries: int = 3,
    allow_mjpeg_fallback: bool = False,
) -> bytes:
    """Fetch one JPEG from phone camera server.

    Prefer /shot.jpg only — MJPEG /video is huge and was causing agent timeouts
    and 'no connection' flapping when used as a fallback every failure.
    """
    base = base_url.rstrip("/")
    # Direct image URL?
    if base.lower().endswith((".jpg", ".jpeg", ".png")):
        return _http_get(base, timeout_s)

    candidates = [
        base + "/shot.jpg",
        base + "/photo.jpg",
        base + "/jpg",
    ]
    last_err: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        for url in candidates:
            try:
                data = _http_get(url, timeout_s)
                if len(data) > 500 and data[:2] == b"\xff\xd8":
                    return data
                last_err = RuntimeError("non-JPEG response from %s (%d bytes)" % (url, len(data)))
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
        # brief backoff between retries
        if attempt + 1 < retries:
            time.sleep(0.15 * (attempt + 1))

    if allow_mjpeg_fallback:
        try:
            return _first_jpeg_from_mjpeg(base + "/video", timeout_s=min(timeout_s, 4.0))
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    raise RuntimeError(
        "Could not fetch phone JPEG from %s (last error: %s). "
        "Keep IP Webcam foreground, screen on, same Wi‑Fi."
        % (base_url, last_err)
    )


def _first_jpeg_from_mjpeg(url: str, timeout_s: float = 5.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ForgeOS-PhoneCam/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        buf = b""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk
            start = buf.find(b"\xff\xd8")
            end = buf.find(b"\xff\xd9", start + 2) if start >= 0 else -1
            if start >= 0 and end >= 0:
                return buf[start : end + 2]
            if len(buf) > 8_000_000:
                break
    raise RuntimeError("no JPEG in MJPEG stream")


def _decode_gray_rows(jpeg: bytes, max_rows: int = 48) -> Tuple[List[float], int, int, float]:
    """Decode JPEG to per-row mean luma. Prefers PIL, then cv2, then macOS sips→BMP."""
    # --- PIL ---
    try:
        from PIL import Image
        import io

        im = Image.open(io.BytesIO(jpeg)).convert("L")
        w, h = im.size
        step = max(1, h // max_rows)
        px = im.load()
        rows: List[float] = []
        bright = 0
        total = 0
        for y in range(0, h, step):
            s = 0.0
            n = 0
            for x in range(0, w, max(1, w // 64)):
                v = float(px[x, y])
                s += v
                n += 1
                total += 1
                if v > 40:
                    bright += 1
            rows.append(s / max(1, n))
        coverage = bright / max(1, total)
        return rows, w, h, coverage
    except Exception as exc:  # noqa: BLE001
        log.debug("PIL decode failed: %s", exc)

    # --- OpenCV ---
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(jpeg, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError("cv2 imdecode failed")
        h, w = img.shape[:2]
        step = max(1, h // max_rows)
        rows = [float(img[y, :: max(1, w // 64)].mean()) for y in range(0, h, step)]
        coverage = float((img > 40).mean())
        return rows, w, h, coverage
    except Exception as exc:  # noqa: BLE001
        log.debug("cv2 decode failed: %s", exc)

    # --- macOS sips → BMP (pure stdlib parse) ---
    try:
        return _decode_via_sips_bmp(jpeg, max_rows=max_rows)
    except Exception as exc:  # noqa: BLE001
        log.debug("sips decode failed: %s", exc)

    w, h = _jpeg_size(jpeg)
    log.warning("Phone JPEG linked but no pixel decoder — scores degraded")
    rows = [128.0] * max_rows
    return rows, w, h, 0.5


def _decode_via_sips_bmp(jpeg: bytes, max_rows: int = 48) -> Tuple[List[float], int, int, float]:
    import os
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        jp = os.path.join(td, "in.jpg")
        bp = os.path.join(td, "out.bmp")
        with open(jp, "wb") as f:
            f.write(jpeg)
        subprocess.check_call(
            ["sips", "-s", "format", "bmp", jp, "--out", bp],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        data = open(bp, "rb").read()
    if data[:2] != b"BM":
        raise RuntimeError("not BMP")
    w = struct.unpack_from("<i", data, 18)[0]
    h = struct.unpack_from("<i", data, 22)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    off = struct.unpack_from("<I", data, 10)[0]
    if bpp != 24 and bpp != 32:
        raise RuntimeError("unsupported bpp %s" % bpp)
    row_pad = (4 - ((abs(w) * (bpp // 8)) % 4)) % 4
    abs_h = abs(h)
    abs_w = abs(w)
    step = max(1, abs_h // max_rows)
    xstep = max(1, abs_w // 64)
    rows: List[float] = []
    bright = 0
    total = 0
    # BMP bottom-up if h>0
    for yi in range(0, abs_h, step):
        y = abs_h - 1 - yi if h > 0 else yi
        s = 0.0
        n = 0
        for x in range(0, abs_w, xstep):
            i = off + y * (abs_w * (bpp // 8) + row_pad) + x * (bpp // 8)
            b, g, r = data[i], data[i + 1], data[i + 2]
            v = 0.299 * r + 0.587 * g + 0.114 * b
            s += v
            n += 1
            total += 1
            if v > 40:
                bright += 1
        rows.append(s / max(1, n))
    coverage = bright / max(1, total)
    return rows, abs_w, abs_h, coverage


def _jpeg_size(jpeg: bytes) -> Tuple[int, int]:
    """Parse SOF0 for dimensions without full decode."""
    i = 2
    while i < len(jpeg) - 8:
        if jpeg[i] != 0xFF:
            i += 1
            continue
        marker = jpeg[i + 1]
        if marker == 0xD8:
            i += 2
            continue
        if marker == 0xD9:
            break
        length = struct.unpack(">H", jpeg[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", jpeg[i + 5 : i + 9])
            return int(w), int(h)
        i += 2 + length
    return 0, 0


def grab_phone_frame(
    base_url: str,
    timeout_s: float = 5.0,
    *,
    decode: bool = True,
    retries: int = 3,
) -> PhoneFrame:
    jpeg = fetch_jpeg(base_url, timeout_s=timeout_s, retries=retries, allow_mjpeg_fallback=False)
    if decode:
        rows, w, h, cov = _decode_gray_rows(jpeg)
    else:
        w, h = _jpeg_size(jpeg)
        rows, cov = [128.0], 0.5
    return PhoneFrame(
        jpeg=jpeg,
        width=w,
        height=h,
        gray_rows=rows,
        coverage=cov,
        ts=time.time(),
    )


def score_phone_frame(base_url: str, timeout_s: float = 3.0) -> FirstLayerResult:
    fr = grab_phone_frame(base_url, timeout_s=timeout_s)
    result = score_from_gray_rows(fr.gray_rows, coverage=fr.coverage)
    # annotate metrics
    result.metrics["phone_w"] = float(fr.width)
    result.metrics["phone_h"] = float(fr.height)
    result.metrics["phone_ts"] = fr.ts
    return result


class PhoneCameraSource:
    """Callable vision source for RealtimeVisionLoop.vision_feature_fn."""

    def __init__(self, base_url: str, timeout_s: float = 5.0, save_dir: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.save_dir = save_dir
        self._n = 0
        self.last_error: Optional[str] = None

    def __call__(self) -> Optional[FirstLayerResult]:
        try:
            fr = grab_phone_frame(self.base_url, timeout_s=self.timeout_s, retries=3)
            self._n += 1
            self.last_error = None
            if self.save_dir and self._n % 20 == 1:
                try:
                    from pathlib import Path

                    p = Path(self.save_dir)
                    p.mkdir(parents=True, exist_ok=True)
                    (p / "phone_last.jpg").write_bytes(fr.jpeg)
                except Exception:  # noqa: BLE001
                    pass
            result = score_from_gray_rows(fr.gray_rows, coverage=fr.coverage)
            result.metrics["phone_w"] = float(fr.width)
            result.metrics["phone_h"] = float(fr.height)
            result.metrics["source"] = 1.0  # phone
            return result
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            log.warning("phone capture failed: %s", exc)
            return None

    def ping(self) -> dict:
        try:
            fr = grab_phone_frame(self.base_url, timeout_s=self.timeout_s)
            return {
                "ok": True,
                "width": fr.width,
                "height": fr.height,
                "jpeg_bytes": len(fr.jpeg),
                "coverage": fr.coverage,
                "url": self.base_url,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "url": self.base_url}
