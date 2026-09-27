"""Background aisstream.io websocket consumer that keeps the latest position per vessel (MMSI)."""

import asyncio
import contextlib
import json
import logging
import time

import websockets

log = logging.getLogger(__name__)

URL = "wss://stream.aisstream.io/v0/stream"
MAX_AGE_S = 3600
MAX_VESSELS = 40000
# The global feed is thousands of messages a second; drop it when nobody has asked for vessels lately.
IDLE_STOP_S = 600

_vessels: dict[int, dict] = {}
_static: dict[int, dict] = {}
_task: asyncio.Task | None = None
_last_access = 0.0
_state = {"connected": False, "messages": 0, "last_error": None, "started_at": None}


def status() -> dict:
    return {**_state, "vessels": len(_vessels)}


def ensure_started(api_key: str) -> None:
    global _task, _last_access
    _last_access = time.time()
    if _task is None or _task.done():
        _state["started_at"] = time.time()
        _task = asyncio.create_task(_run(api_key))


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await _task
        _task = None
    _state["connected"] = False


def _prune(now: float) -> None:
    cutoff = now - MAX_AGE_S
    for mmsi in [m for m, v in _vessels.items() if v["seen"] < cutoff]:
        del _vessels[mmsi]
    for mmsi in [m for m, v in _static.items() if v["seen"] < cutoff]:
        del _static[mmsi]
    for d in (_vessels, _static):
        if len(d) > MAX_VESSELS:
            # Evict down to 90% in one pass so this sort doesn't run on every message at the cap.
            excess = len(d) - int(MAX_VESSELS * 0.9)
            for old in sorted(d, key=lambda k: d[k]["seen"])[:excess]:
                del d[old]


def snapshot(bbox: tuple | None) -> list[dict]:
    _prune(time.time())
    out = []
    for mmsi, v in _vessels.items():
        if bbox:
            w, s, e, n = bbox
            if not (w <= v["lon"] <= e and s <= v["lat"] <= n):
                continue
        static = _static.get(mmsi)
        if static:
            out.append({**v, **{k: static[k] for k in ("ship_type", "destination", "callsign")}})
        else:
            out.append(dict(v))
    return out


def _handle(msg: dict) -> None:
    meta = msg.get("MetaData") or {}
    mmsi = meta.get("MMSI")
    if not mmsi:
        return
    kind = msg.get("MessageType")
    body = (msg.get("Message") or {}).get(kind) or {}
    now = time.time()
    if kind == "ShipStaticData":
        _static[mmsi] = {
            "ship_type": body.get("Type"),
            "destination": (body.get("Destination") or "").strip() or None,
            "callsign": (body.get("CallSign") or "").strip() or None,
            "seen": now,
        }
        if len(_static) > MAX_VESSELS:
            _prune(now)
        return
    lat, lon = meta.get("latitude"), meta.get("longitude")
    if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
        return
    _vessels[mmsi] = {
        "mmsi": mmsi,
        "name": (meta.get("ShipName") or "").strip() or None,
        "lat": lat,
        "lon": lon,
        "sog_kn": body.get("Sog"),
        "cog": body.get("Cog"),
        "heading": body.get("TrueHeading"),
        "nav_status": body.get("NavigationalStatus"),
        "seen": now,
        "url": f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{mmsi}",
    }
    if len(_vessels) > MAX_VESSELS:
        _prune(now)


def _idle() -> bool:
    return time.time() - _last_access > IDLE_STOP_S


async def _run(api_key: str) -> None:
    backoff = 2
    while not _idle():
        try:
            async with websockets.connect(URL, max_size=2**22) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "APIKey": api_key,
                            "BoundingBoxes": [[[-90, -180], [90, 180]]],
                            "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport", "ShipStaticData"],
                        }
                    )
                )
                _state.update(connected=True, last_error=None)
                backoff = 2
                async for raw in ws:
                    _state["messages"] += 1
                    try:
                        _handle(json.loads(raw))
                    except (ValueError, TypeError):
                        continue
                    if _state["messages"] % 1000 == 0 and _idle():
                        log.info("AIS stream idle for %ss, disconnecting", IDLE_STOP_S)
                        return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _state["last_error"] = f"{type(exc).__name__}: {exc}"
            log.warning("AIS stream error: %s", exc)
        finally:
            _state["connected"] = False
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)
