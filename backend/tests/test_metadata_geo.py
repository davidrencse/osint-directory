import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from app.geo.layers import normalise_bbox
from app.main import app
from app.metadata import extract as ex
from app.metadata.strip import strip


@pytest.fixture(autouse=True)
def no_exiftool(monkeypatch):
    # Exercise the built-in extractors regardless of what is installed locally.
    monkeypatch.setattr(ex, "exiftool_available", lambda: False)
    monkeypatch.setattr("app.metadata.strip.shutil.which", lambda _: None)


def _jpeg_with_gps() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "TestCam"
    exif[0x013B] = "Jane Tester"
    exif[0x8825] = {1: "S", 2: (33.0, 51.0, 54.0), 3: "E", 4: (151.0, 12.0, 36.0)}
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_jpeg_extract_and_strip(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(_jpeg_with_gps())
    r = ex.extract(src, "a.jpg")
    assert r["detected_type"] == "image/jpeg"
    assert r["gps"]["lat"] == pytest.approx(-33.865, abs=1e-3)
    assert r["gps"]["lon"] == pytest.approx(151.21, abs=1e-3)
    reasons = {h["reason"] for h in r["highlights"]}
    assert {"Location", "Identity", "Device / software"} <= reasons

    dst = tmp_path / "b.jpg"
    assert strip(src, "image/jpeg", dst) == "jpeg-segments"
    cleaned = ex.extract(dst, "b.jpg")
    assert cleaned["gps"] is None and "IFD0" not in cleaned["groups"]
    with Image.open(dst) as img:
        assert img.size == (32, 32)


def test_png_strip(tmp_path):
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Jane Tester")
    src = tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(src, pnginfo=info)
    assert "Author" in ex.extract(src, "a.png")["groups"]["Container"]
    dst = tmp_path / "b.png"
    strip(src, "image/png", dst)
    assert "Container" not in ex.extract(dst, "b.png")["groups"]


def test_docx_core_properties(tmp_path):
    src = tmp_path / "a.docx"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr(
            "docProps/core.xml",
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Jane Tester</dc:creator>'
            "<cp:lastModifiedBy>J. T.</cp:lastModifiedBy></cp:coreProperties>",
        )
        z.writestr("word/document.xml", "<w:document/>")
    r = ex.extract(src, "a.docx")
    assert r["groups"]["Core"]["creator"] == "Jane Tester"
    dst = tmp_path / "b.docx"
    strip(src, r["detected_type"], dst)
    assert "Core" not in ex.extract(dst, "b.docx")["groups"]


def test_metadata_endpoint_roundtrip():
    client = TestClient(app)
    files = {"file": ("photo.jpg", _jpeg_with_gps(), "image/jpeg")}
    r = client.post("/api/metadata", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["gps"] is not None and body["strippable"] is True
    r = client.post("/api/metadata/strip", files=files)
    assert r.status_code == 200
    assert "photo.clean.jpg" in r.headers["content-disposition"]


def test_recon_requires_authorization():
    client = TestClient(app)
    assert client.get("/api/recon/stream", params={"target": "example.com"}).status_code == 400
    r = client.get("/api/recon/stream", params={"target": "a@b.com", "authorized": True})
    assert r.status_code == 422


def test_recon_scope_enforced():
    client = TestClient(app)
    client.put("/api/settings/scope", json={"entries": ["example.org"]})
    r = client.get("/api/recon/stream", params={"target": "example.com", "authorized": True})
    assert r.status_code == 403


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("-180,-90,180,90", None),
        ("bad", None),
        ("1.5,40.2,5.1,43.9", (0.0, 40.0, 6.0, 44.0)),
    ],
)
def test_bbox(raw, expected):
    assert normalise_bbox(raw) == expected
