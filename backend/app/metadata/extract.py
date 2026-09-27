"""File metadata extraction (metadata2go-style). Uses exiftool when installed, else built-in parsers."""

import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path
from typing import Any

MAGIC = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF8", "image/gif"),
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"BM", "image/bmp"),
    (b"ID3", "audio/mpeg"),
    (b"fLaC", "audio/flac"),
    (b"OggS", "audio/ogg"),
    (b"\x1aE\xdf\xa3", "video/webm"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/x-ole-storage"),
]

# Fields worth flagging so users see what their own file reveals before sharing it.
_HIGHLIGHT_PATTERNS = [
    (re.compile(r"gps|location|latitude|longitude", re.I), "Location"),
    (re.compile(r"author|creator$|lastmodifiedby|last_modified_by|owner|artist|copyright|by-line|company|manager", re.I), "Identity"),
    (re.compile(r"serial|bodyserial|lensserial|uniqueid|imageuniqueid|documentid|instanceid", re.I), "Device / document ID"),
    (re.compile(r"^(make|model|lensmodel|software|producer|creatortool|application|hostcomputer)$", re.I), "Device / software"),
    (re.compile(r"datetimeoriginal|createdate|creationdate|created$|modified$|modifydate", re.I), "Timestamp"),
]
_PATH_RE = re.compile(r"([A-Za-z]:\\Users\\[^\\]+|/home/[^/]+|/Users/[^/]+)")


def detect_type(head: bytes, filename: str) -> str:
    for sig, mime in MAGIC:
        if head.startswith(sig):
            if mime == "application/zip":
                ext = Path(filename).suffix.lower()
                return {
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }.get(ext, mime)
            return mime
    if head[4:8] == b"ftyp":
        return "video/mp4" if head[8:11] != b"hei" else "image/heic"
    if head[:4] == b"RIFF":
        return {b"WEBP": "image/webp", b"WAVE": "audio/wav", b"AVI ": "video/x-msvideo"}.get(head[8:12], "application/riff")
    return "application/octet-stream"


def hashes(path: Path) -> dict[str, str]:
    md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest()}


def _jsonable(v: Any) -> Any:
    if isinstance(v, bytes):
        if len(v) <= 64:
            try:
                s = v.decode("utf-8").strip("\x00 ")
                if s.isprintable():
                    return s
            except UnicodeDecodeError:
                pass
        return f"<{len(v)} bytes>"
    if isinstance(v, (Fraction,)) or type(v).__name__ == "IFDRational":
        try:
            return round(float(v), 6)
        except (ZeroDivisionError, ValueError):
            return None
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v][:64]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in list(v.items())[:200]}
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


# --- exiftool ----------------------------------------------------------------------------------


def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def _exiftool(path: Path) -> tuple[dict, dict | None]:
    out = subprocess.run(
        ["exiftool", "-json", "-G1", "-a", "-s", "-all", "-GPSLatitude#", "-GPSLongitude#", "-GPSAltitude#", str(path)],
        capture_output=True,
        timeout=60,
        check=False,
    )
    rows = json.loads(out.stdout.decode("utf-8", errors="replace") or "[{}]")
    flat = rows[0] if rows else {}
    groups: dict[str, dict] = {}
    gps: dict[str, float] = {}
    for key, value in flat.items():
        if key == "SourceFile":
            continue
        group, _, tag = key.partition(":")
        if not tag:
            group, tag = "File", group
        if group == "System":
            continue  # host filesystem details of the temp copy, not the original file
        groups.setdefault(group, {})[tag] = value
        if tag in ("GPSLatitude", "GPSLongitude", "GPSAltitude") and isinstance(value, (int, float)):
            gps[tag.removeprefix("GPS").lower()] = float(value)
    loc = {"lat": gps["latitude"], "lon": gps["longitude"], "alt": gps.get("altitude")} if {"latitude", "longitude"} <= gps.keys() else None
    return groups, loc


# --- built-in fallbacks -----------------------------------------------------------------------


def _gps_to_decimal(gps: dict) -> dict | None:
    def conv(vals, ref):
        d, m, s = (float(x) for x in vals)
        dec = d + m / 60 + s / 3600
        return -dec if ref in ("S", "W") else dec

    try:
        lat = conv(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
        lon = conv(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    alt = gps.get("GPSAltitude")
    return {"lat": round(lat, 7), "lon": round(lon, 7), "alt": float(alt) if alt is not None else None}


def _image(path: Path) -> tuple[dict, dict | None]:
    from PIL import ExifTags, Image

    groups: dict[str, dict] = {}
    with Image.open(path) as img:
        groups["Image"] = {"Format": img.format, "Width": img.width, "Height": img.height, "Mode": img.mode}
        info = {k: v for k, v in img.info.items() if k not in ("exif", "icc_profile", "xmp")}
        if info:
            groups["Container"] = _jsonable(info)
        if "icc_profile" in img.info:
            groups["Image"]["ICCProfile"] = f"<{len(img.info['icc_profile'])} bytes>"
        if img.info.get("xmp"):
            groups["XMP"] = {"Raw": img.info["xmp"][:4000].decode("utf-8", "replace") if isinstance(img.info["xmp"], bytes) else str(img.info["xmp"])[:4000]}
        exif = img.getexif()
        if exif:
            groups["IFD0"] = {ExifTags.TAGS.get(k, str(k)): _jsonable(v) for k, v in exif.items() if k not in (0x8769, 0x8825)}
            sub = exif.get_ifd(0x8769)
            if sub:
                groups["ExifIFD"] = {ExifTags.TAGS.get(k, str(k)): _jsonable(v) for k, v in sub.items() if k != 0x927C}
            gps_raw = exif.get_ifd(0x8825)
            if gps_raw:
                gps = {ExifTags.GPSTAGS.get(k, str(k)): _jsonable(v) for k, v in gps_raw.items()}
                groups["GPS"] = gps
                return groups, _gps_to_decimal(gps)
    return groups, None


def _pdf(path: Path) -> tuple[dict, dict | None]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    groups: dict[str, dict] = {
        "PDF": {
            "Pages": len(reader.pages),
            "Encrypted": reader.is_encrypted,
            "HeaderVersion": reader.pdf_header,
        }
    }
    meta = reader.metadata or {}
    if meta:
        groups["Info"] = {str(k).lstrip("/"): _jsonable(str(v)) for k, v in meta.items()}
    try:
        xmp = reader.xmp_metadata
    except Exception:
        xmp = None
    if xmp is not None:
        groups["XMP"] = _jsonable(
            {
                "CreatorTool": xmp.xmp_creator_tool,
                "Producer": xmp.pdf_producer,
                "CreateDate": xmp.xmp_create_date,
                "ModifyDate": xmp.xmp_modify_date,
                "DocumentID": xmp.xmpmm_document_id,
                "InstanceID": xmp.xmpmm_instance_id,
                "Creator": xmp.dc_creator,
            }
        )
    return groups, None


def _ooxml(path: Path) -> tuple[dict, dict | None]:
    groups: dict[str, dict] = {}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for part, group in (("docProps/core.xml", "Core"), ("docProps/app.xml", "App"), ("docProps/custom.xml", "Custom")):
            if part not in names:
                continue
            if z.getinfo(part).file_size > 8 * 1024 * 1024:
                raise ValueError(f"{part} is implausibly large")
            root = ET.fromstring(z.read(part))
            fields = {}
            for el in root.iter():
                tag = el.tag.split("}")[-1]
                if group == "Custom" and tag == "property":
                    val = next((c.text for c in el), None)
                    fields[el.get("name", "?")] = val
                elif el.text and el.text.strip() and len(el) == 0:
                    fields[tag] = el.text.strip()
            if fields:
                groups[group] = fields
        groups["Package"] = {"Parts": len(names), "HasMacros": any(n.endswith("vbaProject.bin") for n in names)}
    return groups, None


def _hachoir(path: Path) -> tuple[dict, dict | None]:
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser

    parser = createParser(str(path))
    if not parser:
        return {}, None
    with parser:
        meta = extractMetadata(parser)
    if not meta:
        return {}, None
    fields = {}
    for item in meta:
        if item.values:
            vals = [v.text for v in item.values]
            fields[item.key] = vals[0] if len(vals) == 1 else vals
    return {"Media": fields}, None


def _builtin(path: Path, mime: str) -> tuple[dict, dict | None]:
    if mime.startswith("image/") and mime != "image/heic":
        return _image(path)
    if mime == "application/pdf":
        return _pdf(path)
    if mime.startswith("application/vnd.openxmlformats"):
        return _ooxml(path)
    return _hachoir(path)


# --- entry point ------------------------------------------------------------------------------


def _highlights(groups: dict) -> list[dict]:
    out = []
    for group, fields in groups.items():
        if not isinstance(fields, dict):
            continue
        for tag, value in fields.items():
            if value in (None, "", [], {}):
                continue
            text = str(value)
            reason = next((r for pat, r in _HIGHLIGHT_PATTERNS if pat.search(tag)), None)
            if reason is None and _PATH_RE.search(text):
                reason = "Local file path (may contain a username)"
            if reason:
                out.append({"group": group, "tag": tag, "value": text[:300], "reason": reason})
    return out


def extract(path: Path, filename: str) -> dict:
    with path.open("rb") as f:
        head = f.read(32)
    mime = detect_type(head, filename)
    errors = []
    groups: dict = {}
    gps = None
    extractor = "builtin"
    if exiftool_available():
        try:
            groups, gps = _exiftool(path)
            extractor = "exiftool"
        except Exception as exc:
            errors.append(f"exiftool: {exc}")
    if not groups:
        try:
            groups, gps = _builtin(path, mime)
        except Exception as exc:
            errors.append(f"builtin: {type(exc).__name__}: {exc}")
    return {
        "filename": filename,
        "size": path.stat().st_size,
        "detected_type": mime,
        "hashes": hashes(path),
        "extractor": extractor,
        "groups": groups,
        "gps": gps,
        "highlights": _highlights(groups),
        "strippable": can_strip(mime),
        "errors": errors,
    }


def can_strip(mime: str) -> bool:
    from app.metadata.strip import SUPPORTED

    return exiftool_available() or mime in SUPPORTED
