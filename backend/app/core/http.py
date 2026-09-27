"""Shared async HTTP client with a per-host minimum interval between requests."""

import asyncio
import time
from urllib.parse import urlsplit

import httpx

from app.config import get_settings

_client: httpx.AsyncClient | None = None

# Minimum seconds between requests to the same host. Conservative defaults for free tiers.
_HOST_INTERVAL: dict[str, float] = {
    "crt.sh": 2.0,
    "ipinfo.io": 0.5,
    "api.greynoise.io": 1.0,
    "urlscan.io": 1.0,
    "www.virustotal.com": 15.0,  # public API: 4 req/min
    "api.shodan.io": 1.0,
    "opensky-network.org": 5.0,
}
_host_locks: dict[str, asyncio.Lock] = {}
_host_last: dict[str, float] = {}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(25.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": get_settings().user_agent},
        )
    return _client


async def close() -> None:
    if _client is not None:
        await _client.aclose()


async def _throttle(url: str) -> None:
    host = urlsplit(url).hostname or ""
    interval = _HOST_INTERVAL.get(host)
    if not interval:
        return
    lock = _host_locks.setdefault(host, asyncio.Lock())
    async with lock:
        wait = _host_last.get(host, 0) + interval - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _host_last[host] = time.monotonic()


async def request(method: str, url: str, *, retries: int = 1, **kwargs) -> httpx.Response:
    """Throttled request; retries on connection errors, 429 and 5xx."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        await _throttle(url)
        try:
            resp = await client().request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last_exc = exc
        else:
            if resp.status_code != 429 and resp.status_code < 500:
                return resp
            if attempt == retries:
                return resp
        if attempt < retries:
            await asyncio.sleep(1.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


async def get(url: str, **kwargs) -> httpx.Response:
    return await request("GET", url, **kwargs)


async def get_json(url: str, **kwargs):
    resp = await get(url, **kwargs)
    resp.raise_for_status()
    return resp.json()
