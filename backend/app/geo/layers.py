"""Live map layers. Each returns a GeoJSON FeatureCollection; upstream calls are cached in memory."""

import asyncio
import csv
import io
import time
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import Settings, get_settings
from app.core import http
from app.geo import ais

FC = dict  # GeoJSON FeatureCollection


def _fc(features: list[dict], **meta) -> FC:
    return {"type": "FeatureCollection", "features": features, "meta": meta}


def _point(lon: float, lat: float, props: dict) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


# --- individual layers ------------------------------------------------------------------------


async def earthquakes(settings: Settings, bbox: tuple | None) -> FC:
    d = await http.get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson")
    feats = []
    for f in d.get("features") or []:
        p = f.get("properties") or {}
        feats.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "title": p.get("title"),
                    "mag": p.get("mag"),
                    "place": p.get("place"),
                    "time": p.get("time"),
                    "tsunami": p.get("tsunami"),
                    "alert": p.get("alert"),
                    "depth_km": (f["geometry"].get("coordinates") or [0, 0, 0])[2],
                    "url": p.get("url"),
                },
            }
        )
    return _fc(feats, source="USGS", source_url="https://earthquake.usgs.gov/earthquakes/map/")


async def aircraft(settings: Settings, bbox: tuple | None) -> FC:
    params = None
    if bbox:
        w, s, e, n = bbox
        params = {"lamin": s, "lomin": w, "lamax": n, "lomax": e}
    d = await http.get_json("https://opensky-network.org/api/states/all", params=params, timeout=20.0)
    feats = []
    for sv in d.get("states") or []:
        lon, lat = sv[5], sv[6]
        if lon is None or lat is None:
            continue
        feats.append(
            _point(
                lon,
                lat,
                {
                    "icao24": sv[0],
                    "callsign": (sv[1] or "").strip() or None,
                    "origin_country": sv[2],
                    "altitude_m": sv[13] if sv[13] is not None else sv[7],
                    "on_ground": sv[8],
                    "velocity_ms": sv[9],
                    "heading": sv[10],
                    "vertical_rate": sv[11],
                    "squawk": sv[14],
                    "url": f"https://globe.adsbexchange.com/?icao={sv[0]}",
                },
            )
        )
    return _fc(feats, source="OpenSky Network", source_url="https://opensky-network.org/", time=d.get("time"))


async def ships(settings: Settings, bbox: tuple | None) -> FC:
    if not settings.aisstream_api_key:
        return _fc([], disabled=True, reason="Set AISSTREAM_API_KEY to enable live AIS vessels")
    ais.ensure_started(settings.aisstream_api_key)
    feats = [
        _point(v["lon"], v["lat"], {k: v.get(k) for k in v if k not in ("lat", "lon")})
        for v in ais.snapshot(bbox)
    ]
    return _fc(feats, source="aisstream.io", source_url="https://aisstream.io/", status=ais.status())


async def cables(settings: Settings, bbox: tuple | None) -> FC:
    d = await http.get_json("https://www.submarinecablemap.com/api/v3/cable/cable-geo.json", timeout=30.0)
    for f in d.get("features") or []:
        p = f.get("properties") or {}
        f["properties"] = {
            "name": p.get("name"),
            "color": p.get("color"),
            "url": f"https://www.submarinecablemap.com/submarine-cable/{p.get('id')}" if p.get("id") else None,
        }
    return _fc(d.get("features") or [], source="TeleGeography", source_url="https://www.submarinecablemap.com/")


async def landings(settings: Settings, bbox: tuple | None) -> FC:
    d = await http.get_json(
        "https://www.submarinecablemap.com/api/v3/landing-point/landing-point-geo.json", timeout=30.0
    )
    for f in d.get("features") or []:
        p = f.get("properties") or {}
        f["properties"] = {"name": p.get("name"), "id": p.get("id")}
    return _fc(d.get("features") or [], source="TeleGeography", source_url="https://www.submarinecablemap.com/")


async def fires(settings: Settings, bbox: tuple | None) -> FC:
    if not settings.firms_map_key:
        return _fc([], disabled=True, reason="Set FIRMS_MAP_KEY (free NASA FIRMS key) to enable fires")
    area = "world" if not bbox else ",".join(str(round(v, 2)) for v in bbox)
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{settings.firms_map_key}/VIIRS_NOAA20_NRT/{area}/1"
    resp = await http.get(url, timeout=60.0)
    resp.raise_for_status()
    feats = await asyncio.to_thread(_fire_features, resp.text)
    return _fc(feats, source="NASA FIRMS (VIIRS NOAA-20)", source_url="https://firms.modaps.eosdis.nasa.gov/map/")


def _num(v: str | None) -> float:
    try:
        return float(v or 0)
    except ValueError:
        return 0.0


def _fire_features(text: str) -> list[dict]:
    """Parse the FIRMS CSV (can be tens of MB for the world); malformed rows are skipped, not fatal."""
    feats = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            lon, lat = float(r["longitude"]), float(r["latitude"])
        except (KeyError, TypeError, ValueError):
            continue
        feats.append(
            _point(
                lon,
                lat,
                {
                    "frp_mw": _num(r.get("frp")),
                    "brightness_k": _num(r.get("bright_ti4")),
                    "confidence": r.get("confidence"),
                    "acquired": f"{r.get('acq_date')} {r.get('acq_time')}",
                    "daynight": r.get("daynight"),
                },
            )
        )
    feats.sort(key=lambda f: f["properties"]["frp_mw"], reverse=True)
    return feats[:60000]


async def disasters(settings: Settings, bbox: tuple | None) -> FC:
    d = await http.get_json(
        "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",
        params={"eventlist": "EQ;TC;FL;VO;DR;WF", "alertlevel": "Green;Orange;Red"},
        timeout=30.0,
    )
    feats = []
    for f in d.get("features") or []:
        p = f.get("properties") or {}
        if (f.get("geometry") or {}).get("type") != "Point":
            continue
        feats.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "eventtype": p.get("eventtype"),
                    "name": p.get("name") or p.get("eventname"),
                    "alertlevel": p.get("alertlevel"),
                    "country": p.get("country"),
                    "from": p.get("fromdate"),
                    "to": p.get("todate"),
                    "severity": (p.get("severitydata") or {}).get("severitytext"),
                    "url": (p.get("url") or {}).get("report"),
                },
            }
        )
    return _fc(feats, source="GDACS", source_url="https://www.gdacs.org/")


# CAMEO root codes, used to label GDELT events.
CAMEO_ROOT = {
    "01": "Public statement", "02": "Appeal", "03": "Intent to cooperate", "04": "Consult",
    "05": "Diplomatic cooperation", "06": "Material cooperation", "07": "Provide aid", "08": "Yield",
    "09": "Investigate", "10": "Demand", "11": "Disapprove", "12": "Reject", "13": "Threaten",
    "14": "Protest", "15": "Force posture", "16": "Reduce relations", "17": "Coerce", "18": "Assault",
    "19": "Fight", "20": "Mass violence",
}
INCIDENT_ROOTS = {"14", "15", "17", "18", "19", "20"}


_GDELT_TTL_S = 600
_gdelt_cache: tuple[float, list[list[str]]] | None = None
_gdelt_lock = asyncio.Lock()


def _unzip_rows(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    return [row for row in csv.reader(io.StringIO(text), delimiter="\t") if len(row) >= 61]


async def _gdelt_rows() -> list[list[str]]:
    """The last hour of GDELT rows, downloaded once and shared by the news and incidents layers."""
    global _gdelt_cache
    async with _gdelt_lock:
        if _gdelt_cache and _gdelt_cache[0] > time.time():
            return _gdelt_cache[1]
        rows = await _fetch_gdelt_rows()
        _gdelt_cache = (time.time() + _GDELT_TTL_S, rows)
        return rows


async def _fetch_gdelt_rows(windows: int = 4) -> list[list[str]]:
    """Rows from the latest `windows` 15-minute GDELT 2.0 event exports (1 hour by default)."""
    last = await http.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt", timeout=15.0)
    last.raise_for_status()
    export_url = next(line.split()[-1] for line in last.text.splitlines() if ".export." in line)
    stamp = datetime.strptime(export_url.rsplit("/", 1)[1][:14], "%Y%m%d%H%M%S")
    urls = [
        f"http://data.gdeltproject.org/gdeltv2/{(stamp - timedelta(minutes=15 * i)):%Y%m%d%H%M%S}.export.CSV.zip"
        for i in range(windows)
    ]

    async def fetch(u: str) -> list[list[str]]:
        try:
            r = await http.get(u, timeout=30.0, retries=0)
            r.raise_for_status()
        except Exception:
            return []
        try:
            return await asyncio.to_thread(_unzip_rows, r.content)
        except (zipfile.BadZipFile, IndexError):
            return []

    batches = await asyncio.gather(*(fetch(u) for u in urls))
    return [row for b in batches for row in b]


async def _gdelt_layer(incidents_only: bool) -> FC:
    rows = await _gdelt_rows()
    seen: set[str] = set()
    feats = []
    for r in rows:
        root, url = r[28], r[60]
        if incidents_only and root not in INCIDENT_ROOTS:
            continue
        if not r[56] or not r[57] or url in seen:
            continue
        seen.add(url)
        try:
            lat, lon = float(r[56]), float(r[57])
            goldstein, tone, mentions = float(r[30] or 0), round(float(r[34] or 0), 2), int(r[31] or 0)
        except ValueError:
            continue
        feats.append(
            _point(
                lon,
                lat,
                {
                    "event": CAMEO_ROOT.get(root, root),
                    "code": r[26],
                    "actor1": r[6] or None,
                    "actor2": r[16] or None,
                    "place": r[52],
                    "country": r[53],
                    "goldstein": goldstein,
                    "tone": tone,
                    "mentions": mentions,
                    "added": r[59],
                    "url": url,
                },
            )
        )
    return _fc(feats, source="GDELT 2.0 events (last hour)", source_url="https://www.gdeltproject.org/")


async def news(settings: Settings, bbox: tuple | None) -> FC:
    return await _gdelt_layer(incidents_only=False)


async def incidents(settings: Settings, bbox: tuple | None) -> FC:
    return await _gdelt_layer(incidents_only=True)


async def iss(settings: Settings, bbox: tuple | None) -> FC:
    d = await http.get_json("https://api.wheretheiss.at/v1/satellites/25544", timeout=10.0)
    return _fc(
        [
            _point(
                d["longitude"],
                d["latitude"],
                {
                    "name": "ISS",
                    "altitude_km": round(d.get("altitude", 0), 1),
                    "velocity_kmh": round(d.get("velocity", 0)),
                    "visibility": d.get("visibility"),
                },
            )
        ],
        source="wheretheiss.at",
        source_url="https://wheretheiss.at/",
    )


# --- registry & cache -------------------------------------------------------------------------


@dataclass(frozen=True)
class Layer:
    id: str
    label: str
    group: str
    ttl_s: float
    fetch: Callable[[Settings, tuple | None], Awaitable[FC]]
    key_field: str | None = None
    uses_bbox: bool = False
    refresh_s: float = 0  # how often the frontend should poll; 0 = load once
    description: str = ""


LAYERS: dict[str, Layer] = {
    l.id: l
    for l in [
        Layer("earthquakes", "Earthquakes (24h)", "hazards", 60, earthquakes, refresh_s=120,
              description="USGS all earthquakes, past day"),
        Layer("disasters", "Disaster alerts", "hazards", 600, disasters, refresh_s=900,
              description="GDACS cyclones, floods, volcanoes, wildfires, droughts"),
        Layer("fires", "Active fires", "hazards", 1800, fires, key_field="firms_map_key", refresh_s=1800,
              description="NASA FIRMS VIIRS thermal detections, past day"),
        Layer("aircraft", "Aircraft (ADS-B)", "transport", 15, aircraft, uses_bbox=True, refresh_s=30,
              description="OpenSky Network live state vectors in view"),
        Layer("ships", "Vessels (AIS)", "transport", 10, ships, key_field="aisstream_api_key", uses_bbox=True,
              refresh_s=20, description="aisstream.io live AIS positions"),
        Layer("iss", "ISS position", "transport", 5, iss, refresh_s=10, description="International Space Station"),
        Layer("cables", "Submarine cables", "infrastructure", 86400, cables,
              description="TeleGeography submarine cable routes"),
        Layer("landings", "Cable landing points", "infrastructure", 86400, landings,
              description="TeleGeography cable landing stations"),
        Layer("news", "News events", "intel", 900, news, refresh_s=900,
              description="Geocoded GDELT news events, last hour"),
        Layer("incidents", "Conflict & unrest", "intel", 900, incidents, refresh_s=900,
              description="GDELT protest, coercion, assault and fighting events, last hour"),
    ]
}

_cache: dict[str, tuple[float, FC]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _bbox_key(bbox: tuple | None) -> str:
    return "world" if bbox is None else ",".join(str(v) for v in bbox)


def normalise_bbox(raw: str | None) -> tuple | None:
    """Parse 'west,south,east,north' and snap outward to a 2-degree grid so nearby views share a cache."""
    if not raw:
        return None
    try:
        w, s, e, n = (float(x) for x in raw.split(","))
    except ValueError:
        return None
    w, e = max(-180.0, w), min(180.0, e)
    s, n = max(-90.0, s), min(90.0, n)
    if e - w >= 300 or n - s >= 150 or w >= e or s >= n:
        return None  # whole world or antimeridian-crossing view
    snap = 2.0
    return (
        float(int(w // snap) * snap),
        float(int(s // snap) * snap),
        float(-int(-e // snap) * snap),
        float(-int(-n // snap) * snap),
    )


async def get_layer(layer_id: str, bbox: tuple | None) -> FC:
    layer = LAYERS[layer_id]
    bbox = bbox if layer.uses_bbox else None
    key = f"{layer_id}:{_bbox_key(bbox)}"
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    async with _locks.setdefault(key, asyncio.Lock()):
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        fc = await layer.fetch(get_settings(), bbox)
        fc["meta"]["fetched_at"] = datetime.now(timezone.utc).isoformat()
        fc["meta"]["count"] = len(fc["features"])
        _cache[key] = (time.time() + layer.ttl_s, fc)
        if len(_cache) > 200:  # drop expired bbox variants and their idle locks
            now = time.time()
            for k in [k for k, (exp, _) in _cache.items() if exp < now]:
                _cache.pop(k, None)
                lock = _locks.get(k)
                if lock is not None and not lock.locked():
                    del _locks[k]
        return fc


def describe(settings: Settings) -> list[dict]:
    return [
        {
            "id": l.id,
            "label": l.label,
            "group": l.group,
            "refresh_s": l.refresh_s,
            "uses_bbox": l.uses_bbox,
            "description": l.description,
            "enabled": not l.key_field or bool(getattr(settings, l.key_field)),
            "key_field": l.key_field,
        }
        for l in LAYERS.values()
    ]
