"""Routing (RIPEstat) and IP geolocation (ipinfo)."""

import asyncio

from app.config import Settings
from app.core import http
from app.recon.base import Output, Pipeline, Pivot, query_type, query_value
from app.recon.classify import InputType, Target

RIPESTAT = "https://stat.ripe.net/data/{}/data.json"


async def _stat(endpoint: str, resource: str) -> dict:
    body = await http.get_json(RIPESTAT.format(endpoint), params={"resource": resource})
    return body.get("data") or {}


class RipeStat(Pipeline):
    name = "ripestat"
    label = "BGP routing (RIPEstat)"
    category = "network"
    accepts = frozenset({InputType.IP, InputType.CIDR, InputType.ASN})
    homepage = "https://stat.ripe.net/"

    async def run(self, target: Target, settings: Settings) -> Output:
        kind = query_type(target, self)
        value = query_value(target, self)
        source = f"https://stat.ripe.net/{value}"

        if kind == InputType.ASN:
            overview, prefixes, neighbours = await asyncio.gather(
                _stat("as-overview", value),
                _stat("announced-prefixes", value),
                _stat("asn-neighbours", value),
            )
            pfx = [p["prefix"] for p in prefixes.get("prefixes") or []]
            neigh = neighbours.get("neighbours") or []
            return Output(
                summary={
                    "holder": overview.get("holder"),
                    "announced": overview.get("announced"),
                    "prefixes_v4": sum(1 for p in pfx if ":" not in p),
                    "prefixes_v6": sum(1 for p in pfx if ":" in p),
                    "upstreams": sum(1 for n in neigh if n.get("type") == "left"),
                    "downstreams": sum(1 for n in neigh if n.get("type") == "right"),
                },
                data={"overview": overview, "prefixes": pfx, "neighbours": neigh},
                source_url=source,
                pivots=[Pivot(InputType.CIDR, p, "announced") for p in pfx[:60]],
            )

        overview, abuse, rpki_ctx = await asyncio.gather(
            _stat("prefix-overview", value),
            _stat("abuse-contact-finder", value),
            _stat("routing-status", value),
            return_exceptions=True,
        )
        if isinstance(overview, Exception):
            raise overview
        asns = overview.get("asns") or []
        summary = {
            "prefix": overview.get("resource"),
            "announced": overview.get("announced"),
            "asns": [f"AS{a['asn']} {a.get('holder', '')}".strip() for a in asns],
            "abuse_contacts": abuse.get("abuse_contacts") if isinstance(abuse, dict) else None,
        }
        if isinstance(rpki_ctx, dict):
            summary["first_seen"] = (rpki_ctx.get("first_seen") or {}).get("time")
            summary["visibility_v4"] = (rpki_ctx.get("visibility") or {}).get("v4", {}).get("ris_peers_seeing")
        pivots = [Pivot(InputType.ASN, f"AS{a['asn']}", a.get("holder", "")) for a in asns]
        if overview.get("resource") and overview.get("resource") != value:
            pivots.append(Pivot(InputType.CIDR, overview["resource"], "covering prefix"))
        return Output(
            summary=summary,
            data={"overview": overview, "abuse": abuse if isinstance(abuse, dict) else None},
            source_url=source,
            pivots=pivots,
        )


class IpInfo(Pipeline):
    name = "geoip"
    label = "IP geolocation (ipinfo)"
    category = "network"
    accepts = frozenset({InputType.IP})
    key_fields = ("ipinfo_token",)
    optional_key = True
    homepage = "https://ipinfo.io/"

    async def run(self, target: Target, settings: Settings) -> Output:
        ip = query_value(target, self)
        params = {"token": settings.ipinfo_token} if settings.ipinfo_token else None
        data = await http.get_json(f"https://ipinfo.io/{ip}/json", params=params)
        lat, lon = (data.get("loc") or ",").split(",")
        return Output(
            summary={
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country"),
                "org": data.get("org"),
                "hostname": data.get("hostname"),
                "anycast": data.get("anycast", False),
                "bogon": data.get("bogon", False),
            },
            data={**data, "lat": float(lat) if lat else None, "lon": float(lon) if lon else None},
            source_url=f"https://ipinfo.io/{ip}",
            pivots=[Pivot(InputType.DOMAIN, data["hostname"], "hostname")] if data.get("hostname") else [],
        )
