"""Regression tests for unbounded growth and malformed-input handling."""

import io
import time
import zipfile

import pytest

from app.core import store
from app.geo import ais
from app.metadata.strip import StripError, _jpeg, _ooxml, _png


def test_expired_cache_rows_are_purged(tmp_path):
    store.cache_set("old", {"v": 1}, ttl_s=-10)
    store.cache_set("live", {"v": 2}, ttl_s=3600)
    store.use_database(tmp_path / "test.db")  # reopening sweeps expired rows
    with store._lock:
        keys = [r[0] for r in store._db().execute("SELECT key FROM cache").fetchall()]
    assert keys == ["live"]


def test_cache_set_purges_periodically():
    store.cache_set("stale", 1, ttl_s=-10)
    for i in range(store._PURGE_EVERY):
        store.cache_set(f"k{i}", i, ttl_s=3600)
    with store._lock:
        stale = store._db().execute("SELECT count(*) FROM cache WHERE key = 'stale'").fetchone()[0]
    assert stale == 0


@pytest.fixture
def clean_ais(monkeypatch):
    monkeypatch.setattr(ais, "_vessels", {})
    monkeypatch.setattr(ais, "_static", {})
    monkeypatch.setattr(ais, "MAX_VESSELS", 100)


def _pos(mmsi: int) -> dict:
    return {"MessageType": "PositionReport", "MetaData": {"MMSI": mmsi, "latitude": 1.0, "longitude": 2.0}, "Message": {}}


def _static(mmsi: int) -> dict:
    return {"MessageType": "ShipStaticData", "MetaData": {"MMSI": mmsi}, "Message": {"ShipStaticData": {"CallSign": "X"}}}


def test_ais_vessel_and_static_tables_stay_bounded(clean_ais):
    for m in range(1, 1000):
        ais._handle(_pos(m))
        ais._handle(_static(m + 5000))  # static data for ships never seen moving
    assert len(ais._vessels) <= 100
    assert len(ais._static) <= 100


def test_ais_snapshot_drops_stale_static(clean_ais):
    ais._handle(_static(7))
    ais._static[7]["seen"] = time.time() - ais.MAX_AGE_S - 1
    ais.snapshot(None)
    assert 7 not in ais._static


def test_ais_snapshot_merges_static_without_seen(clean_ais):
    ais._handle(_pos(9))
    ais._handle(_static(9))
    (v,) = ais.snapshot(None)
    assert v["callsign"] == "X" and v["mmsi"] == 9


def test_jpeg_fill_bytes_and_truncation():
    body = b"\xff\xd8" + b"\xff\xff\xe1\x00\x04ab" + b"\xff\xda\x00\x02scan\xff\xd9"
    out = _jpeg(body)
    assert b"ab" not in out and out.endswith(b"scan\xff\xd9")
    with pytest.raises(StripError):
        _jpeg(b"\xff\xd8\xff\xe1\x00\x50short")
    with pytest.raises(StripError):
        _jpeg(b"\xff\xd8\xff")


def test_png_truncation_raises_strip_error():
    with pytest.raises(StripError):
        _png(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x50IHDR")


def _docx(tmp_path, custom: bytes, app: bytes):
    src = tmp_path / "in.docx"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("docProps/custom.xml", custom)
        z.writestr("docProps/app.xml", app)
        z.writestr("word/document.xml", b"<w:document/>" * 1000)
    return src


def test_ooxml_strip_keeps_xml_well_formed(tmp_path):
    import xml.etree.ElementTree as ET

    empty_custom = b'<?xml version="1.0"?><Properties xmlns="urn:x"/>'
    full_custom = b'<Properties xmlns="urn:x"><property name="Client"><vt>ACME</vt></property></Properties>'
    app = b"<Properties><Company>ACME Corp</Company><Manager>Pat</Manager><Pages>3</Pages></Properties>"
    for custom in (empty_custom, full_custom):
        src, dst = _docx(tmp_path, custom, app), tmp_path / "out.docx"
        _ooxml(src, dst)
        with zipfile.ZipFile(dst) as z:
            ET.fromstring(z.read("docProps/custom.xml"))  # must still parse
            assert b"ACME" not in z.read("docProps/custom.xml")
            app_out = z.read("docProps/app.xml")
            assert b"ACME" not in app_out and b"Pat" not in app_out and b"<Pages>3</Pages>" in app_out
            assert z.read("word/document.xml") == b"<w:document/>" * 1000


def test_ooxml_rejects_oversized_props_part(tmp_path):
    src = tmp_path / "bomb.docx"
    with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("docProps/app.xml", b"\0" * (9 * 1024 * 1024))
    with pytest.raises(StripError):
        _ooxml(src, tmp_path / "out.docx")


def test_strip_endpoint_returns_422_for_corrupt_office_file():
    from fastapi.testclient import TestClient

    from app.main import app

    files = {"file": ("broken.docx", io.BytesIO(b"PK\x03\x04 not really a zip"), "application/octet-stream")}
    r = TestClient(app).post("/api/metadata/strip", files=files)
    assert r.status_code in (415, 422)
