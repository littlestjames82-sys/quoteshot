"""Photo records: filename, size, sha256, format, dimensions, EXIF basics.

Stdlib only. This module *reads file headers* - it does not analyse image
content. No object detection, no measurement from pixels, no judgement.

Supported:
- JPEG: SOF0/SOF2 dimensions, APP1 Exif TIFF (IFD0 Make/Model/DateTime,
  Exif IFD DateTimeOriginal + pixel dimensions, GPS IFD lat/lon when the
  photo already carries them).
- PNG: IHDR dimensions.
- GIF: logical screen dimensions.
Anything else is rejected by name. Every EXIF field fails soft: a
malformed offset yields None for that field, never an exception that
loses the photo.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from .money import QuoteShotError

# ---------------------------------------------------------------------------
# public API

def describe_photo(path: Path) -> dict:
    """Return the photo record dict for a file (no copying done here).

    The record holds ``filename``, ``size_bytes``, ``sha256``,
    ``format`` (``jpeg`` / ``png`` / ``gif``), ``width`` / ``height``,
    ``captured_at``, ``camera_make`` / ``camera_model``, ``has_exif``,
    and ``has_gps`` / ``gps_lat`` / ``gps_lon``. Fields a file does
    not carry are None, never guessed. Non-images are rejected.
    """
    path = Path(path)
    if not path.is_file():
        raise QuoteShotError(f"photo not found: {path}")
    data_head = path.read_bytes()
    fmt, width, height, exif = _parse_image(data_head, path.name)
    return {
        "filename": path.name,
        "size_bytes": len(data_head),
        "sha256": hashlib.sha256(data_head).hexdigest(),
        "format": fmt,
        "width": width,
        "height": height,
        "captured_at": exif.get("captured_at"),
        "camera_make": exif.get("camera_make"),
        "camera_model": exif.get("camera_model"),
        "has_gps": bool(exif.get("gps_lat") is not None and exif.get("gps_lon") is not None),
        "gps_lat": exif.get("gps_lat"),
        "gps_lon": exif.get("gps_lon"),
        "has_exif": bool(exif),
    }


def _parse_image(data: bytes, name: str):
    if data[:2] == b"\xff\xd8":
        w, h, exif = _parse_jpeg(data)
        return "jpeg", w, h, exif
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = _parse_png(data)
        return "png", w, h, {}
    if data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = _parse_gif(data)
        return "gif", w, h, {}
    raise QuoteShotError(
        f"{name}: not a recognised image (v0.1 supports JPEG, PNG, GIF)")


# ---------------------------------------------------------------------------
# PNG / GIF

def _dim(value: int):
    """A dimension of 0 is a malformed header, not a measurement: it
    fails soft to None, exactly as the JPEG SOF path already did
    (polish A3 - PNG/GIF used to record a literal 0)."""
    return int(value) if value else None


def _parse_png(data: bytes):
    try:
        if data[12:16] != b"IHDR":
            return None, None
        w, h = struct.unpack(">II", data[16:24])
        return _dim(w), _dim(h)
    except Exception:
        return None, None


def _parse_gif(data: bytes):
    try:
        w, h = struct.unpack("<HH", data[6:10])
        return _dim(w), _dim(h)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# JPEG + EXIF

_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _parse_jpeg(data: bytes):
    width = height = None
    exif: dict = {}
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:  # start of scan: headers are done
            break
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if seg_len < 2 or i + 2 + seg_len > n + 2:
            break
        seg = data[i + 4:i + 2 + seg_len]
        if marker in _SOF_MARKERS and len(seg) >= 5:
            height = struct.unpack(">H", seg[1:3])[0]
            width = struct.unpack(">H", seg[3:5])[0]
        elif marker == 0xE1 and seg[:6] == b"Exif\x00\x00":
            exif = _parse_exif_tiff(seg[6:])
        i += 2 + seg_len
    return (int(width) if width else None,
            int(height) if height else None, exif)


_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


class _Tiff:
    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 8:
            raise ValueError("short tiff")
        bo = data[:2]
        self.endian = "<" if bo == b"II" else ">" if bo == b"MM" else None
        if self.endian is None:
            raise ValueError("bad byte order")
        if self.u16(2) != 42:
            raise ValueError("bad tiff magic")

    def u16(self, off):
        return struct.unpack_from(self.endian + "H", self.data, off)[0]

    def u32(self, off):
        return struct.unpack_from(self.endian + "I", self.data, off)[0]

    def ifd(self, off):
        """Parse one IFD into {tag: (type, count, raw_value_bytes_or_offset)}."""
        out = {}
        if off is None or off + 2 > len(self.data):
            return out
        count = self.u16(off)
        for k in range(count):
            entry = off + 2 + k * 12
            if entry + 12 > len(self.data):
                break
            tag, typ, cnt = struct.unpack_from(self.endian + "HHI", self.data, entry)
            out[tag] = (typ, cnt, entry + 8)
        return out

    def raw(self, typ, cnt, val_off):
        size = _TYPE_SIZES.get(typ, 1) * cnt
        if size <= 4:
            return self.data[val_off:val_off + size]
        real = self.u32(val_off)
        return self.data[real:real + size]

    def ascii(self, entry):
        if entry is None:
            return None
        typ, cnt, val_off = entry
        try:
            raw = self.raw(typ, cnt, val_off)
            text = raw.split(b"\x00")[0].decode("ascii", errors="replace").strip()
            return text or None
        except Exception:
            return None

    def rationals(self, entry):
        if entry is None:
            return []
        typ, cnt, val_off = entry
        try:
            raw = self.raw(typ, cnt, val_off)
            vals = []
            fmt = "II" if typ == 5 else "ii"
            for k in range(cnt):
                num, den = struct.unpack_from(self.endian + fmt, raw, k * 8)
                if not den:
                    # A zero denominator makes the rational undefined,
                    # not 0: returning 0.0 used to fabricate a GPS
                    # component (e.g. seconds) the photo never carried.
                    return []
                vals.append(num / den)
            return vals
        except Exception:
            return []

    def u32_value(self, entry):
        if entry is None:
            return None
        typ, cnt, val_off = entry
        try:
            raw = self.raw(typ, cnt, val_off)
            if typ == 3:
                return struct.unpack_from(self.endian + "H", raw, 0)[0]
            if typ in (4, 9):
                return struct.unpack_from(self.endian + "I", raw, 0)[0]
            if typ in (1, 7) and raw:
                return raw[0]
        except Exception:
            return None
        return None


def _parse_exif_tiff(data: bytes) -> dict:
    out: dict = {}
    try:
        t = _Tiff(data)
        ifd0_off = t.u32(4)
        ifd0 = t.ifd(ifd0_off)
        make = t.ascii(ifd0.get(0x010F))
        model = t.ascii(ifd0.get(0x0110))
        dt = t.ascii(ifd0.get(0x0132))
        if make:
            out["camera_make"] = make
        if model:
            out["camera_model"] = model
        if dt:
            out["captured_at"] = dt
        # Exif IFD: DateTimeOriginal preferred over IFD0 DateTime.
        exif_ptr = t.u32_value(ifd0.get(0x8769))
        if exif_ptr:
            exif_ifd = t.ifd(exif_ptr)
            dto = t.ascii(exif_ifd.get(0x9003))
            if dto:
                out["captured_at"] = dto
        # GPS IFD.
        gps_ptr = t.u32_value(ifd0.get(0x8825))
        if gps_ptr:
            gps = t.ifd(gps_ptr)
            lat_ref = t.ascii(gps.get(1))
            lat = t.rationals(gps.get(2))
            lon_ref = t.ascii(gps.get(3))
            lon = t.rationals(gps.get(4))
            if len(lat) == 3 and len(lon) == 3:
                # DMS components must be in range: minutes/seconds of
                # 999 (or a latitude of 999 degrees) used to be folded
                # into a plausible-looking but invented coordinate.
                dms_ok = all(0 <= part[1] < 60 and 0 <= part[2] < 60
                             and part[0] >= 0 for part in (lat, lon))
                la = lat[0] + lat[1] / 60 + lat[2] / 3600
                lo = lon[0] + lon[1] / 60 + lon[2] / 3600
                if (lat_ref or "N").upper().startswith("S"):
                    la = -la
                if (lon_ref or "E").upper().startswith("W"):
                    lo = -lo
                if dms_ok and abs(la) <= 90 and abs(lo) <= 180:
                    out["gps_lat"] = round(la, 7)
                    out["gps_lon"] = round(lo, 7)
    except Exception:
        # Fail soft per photo, per PLAN: record what parsed, invent nothing.
        return out
    return out
