"""Remove metadata from a file. Lossless where possible (JPEG/PNG segments are dropped, not re-encoded)."""

import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

# JPEG APPn markers to drop: APP1 (EXIF/XMP), APP12 (Ducky), APP13 (IPTC/Photoshop), COM
_JPEG_DROP = {0xE1, 0xEC, 0xED, 0xFE}
# PNG ancillary chunks carrying metadata
_PNG_DROP = {b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"}

_EMPTY_CORE = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    b'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
    b'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>'
)

SUPPORTED = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class StripError(Exception):
    pass


def _jpeg(data: bytes) -> bytes:
    if data[:2] != b"\xff\xd8":
        raise StripError("Not a JPEG")
    out = bytearray(b"\xff\xd8")
    i = 2
    while i < len(data):
        if data[i] != 0xFF or i + 1 >= len(data):
            raise StripError("Corrupt JPEG marker stream")
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte before a marker (allowed by the spec)
            i += 1
            continue
        if marker == 0xDA:  # start of scan: copy the rest verbatim
            out += data[i:]
            break
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            out += data[i : i + 2]
            i += 2
            if marker == 0xD9:
                break
            continue
        if i + 4 > len(data):
            raise StripError("Truncated JPEG segment")
        (length,) = struct.unpack(">H", data[i + 2 : i + 4])
        if length < 2 or i + 2 + length > len(data):
            raise StripError("Truncated JPEG segment")
        if marker not in _JPEG_DROP:
            out += data[i : i + 2 + length]
        i += 2 + length
    return bytes(out)


def _png(data: bytes) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(sig):
        raise StripError("Not a PNG")
    out = bytearray(sig)
    i = len(sig)
    while i < len(data):
        if i + 12 > len(data):
            raise StripError("Truncated PNG chunk")
        (length,) = struct.unpack(">I", data[i : i + 4])
        ctype = data[i + 4 : i + 8]
        if i + 12 + length > len(data):
            raise StripError("Truncated PNG chunk")
        if ctype not in _PNG_DROP:
            out += data[i : i + 12 + length]
        i += 12 + length
        if ctype == b"IEND":
            break
    return bytes(out)


def _pdf(src: Path, dst: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(src))
    if reader.is_encrypted:
        raise StripError("Encrypted PDFs are not supported")
    writer = PdfWriter(clone_from=reader)
    writer.metadata = None
    root = writer._root_object
    if "/Metadata" in root:
        del root["/Metadata"]
    with dst.open("wb") as f:
        writer.write(f)


_CUSTOM_PROPS_RE = re.compile(rb"<property\b.*?</property>", re.S)
# Identity fields in docProps/app.xml; emptied rather than removed so the part stays schema-valid.
_APP_IDENTITY_RE = re.compile(rb"<(Company|Manager|HyperlinkBase)>[^<]*</\1>")


_MAX_PROPS_PART = 8 * 1024 * 1024  # docProps parts are a few KB; anything this big is hostile


def _ooxml(src: Path, dst: Path) -> None:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.startswith("docProps/") and item.file_size > _MAX_PROPS_PART:
                raise StripError(f"{item.filename} is implausibly large")
            if item.filename == "docProps/core.xml":
                zout.writestr(item, _EMPTY_CORE)
            elif item.filename == "docProps/custom.xml":
                zout.writestr(item, _CUSTOM_PROPS_RE.sub(b"", zin.read(item)))
            elif item.filename == "docProps/app.xml":
                zout.writestr(item, _APP_IDENTITY_RE.sub(rb"<\1></\1>", zin.read(item)))
            else:
                # Stream the rest: reading every part into memory lets a small zip bomb exhaust RAM.
                with zin.open(item) as fin, zout.open(item, "w") as fout:
                    shutil.copyfileobj(fin, fout, 1 << 20)


def strip(src: Path, mime: str, dst: Path) -> str:
    """Write a cleaned copy of `src` to `dst`. Returns the method used."""
    if shutil.which("exiftool"):
        shutil.copyfile(src, dst)
        proc = subprocess.run(
            ["exiftool", "-all=", "-overwrite_original", str(dst)], capture_output=True, timeout=60
        )
        if proc.returncode == 0:
            return "exiftool"
    if mime == "image/jpeg":
        dst.write_bytes(_jpeg(src.read_bytes()))
        return "jpeg-segments"
    if mime == "image/png":
        dst.write_bytes(_png(src.read_bytes()))
        return "png-chunks"
    if mime == "application/pdf":
        _pdf(src, dst)
        return "pdf-info-xmp"
    if mime.startswith("application/vnd.openxmlformats"):
        _ooxml(src, dst)
        return "ooxml-docprops"
    raise StripError(f"Stripping {mime} requires exiftool to be installed")
