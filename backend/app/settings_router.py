import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.core import store
from app.geo.layers import LAYERS
from app.recon.pipelines import ALL

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Where to get each key; shown on the Settings page.
KEY_SIGNUP = {
    "shodan_api_key": "https://account.shodan.io/",
    "censys_api_token": "https://platform.censys.io/account/api",
    "censys_api_id": "https://search.censys.io/account/api",
    "censys_api_secret": "https://search.censys.io/account/api",
    "virustotal_api_key": "https://www.virustotal.com/gui/my-apikey",
    "abuseipdb_api_key": "https://www.abuseipdb.com/account/api",
    "greynoise_api_key": "https://viz.greynoise.io/account/api-key",
    "otx_api_key": "https://otx.alienvault.com/api",
    "urlscan_api_key": "https://urlscan.io/user/profile/",
    "securitytrails_api_key": "https://securitytrails.com/app/account/credentials",
    "ipinfo_token": "https://ipinfo.io/account/token",
    "firms_map_key": "https://firms.modaps.eosdis.nasa.gov/api/map_key/",
    "aisstream_api_key": "https://aisstream.io/apikeys",
}


class ScopeBody(BaseModel):
    entries: list[str]


@router.get("/keys")
def key_status():
    s = get_settings()
    used_by: dict[str, list[str]] = {}
    for p in ALL:
        for f in p.key_fields:
            used_by.setdefault(f, []).append(p.label)
    for layer in LAYERS.values():
        if layer.key_field:
            used_by.setdefault(layer.key_field, []).append(f"Map: {layer.label}")
    return [
        {
            "field": field,
            "env": field.upper(),
            "set": bool(getattr(s, field)),
            "used_by": used_by.get(field, []),
            "signup": url,
        }
        for field, url in KEY_SIGNUP.items()
    ]


@router.get("/scope")
def get_scope():
    return {"entries": store.scope_list()}


@router.put("/scope")
async def put_scope(body: ScopeBody):
    entries = await asyncio.to_thread(store.scope_replace, body.entries)
    await asyncio.to_thread(store.audit, "scope", "-", {"entries": entries})
    return {"entries": entries}


@router.get("/audit")
def audit(limit: int = 200):
    return store.audit_list(min(limit, 1000))


@router.delete("/cache")
async def clear_cache():
    return {"deleted": await asyncio.to_thread(store.cache_clear)}
