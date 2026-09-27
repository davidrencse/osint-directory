"""Threat-intelligence and internet-scan sources. Most need a (free-tier) API key."""

import base64
import ipaddress

from app.config import Settings
from app.core import http
from app.recon.base import Output, Pipeline, Pivot, query_type, query_value
from app.recon.classify import InputType, Target


def _not_found(url: str, **extra) -> Output:
    return Output(summary={"found": False, **extra}, source_url=url)


class Shodan(Pipeline):
    name = "shodan"
    label = "Shodan"
    category = "threat-intel"
    accepts = frozenset({InputType.IP, InputType.DOMAIN})
    key_fields = ("shodan_api_key",)
    homepage = "https://www.shodan.io/"

    async def run(self, target: Target, settings: Settings) -> Output:
        value = query_value(target, self)
        key = {"key": settings.shodan_api_key}
        if query_type(target, self) == InputType.DOMAIN:
            resp = await http.get(f"https://api.shodan.io/dns/domain/{value}", params=key)
            if resp.status_code == 404:
                return _not_found(f"https://www.shodan.io/domain/{value}")
            resp.raise_for_status()
            d = resp.json()
            subs = sorted({f"{s}.{value}" for s in d.get("subdomains") or []})
            return Output(
                summary={"subdomains": len(subs), "tags": d.get("tags")},
                data=d,
                source_url=f"https://www.shodan.io/domain/{value}",
                pivots=[Pivot(InputType.DOMAIN, s, "Shodan DNS") for s in subs[:100]],
            )

        resp = await http.get(f"https://api.shodan.io/shodan/host/{value}", params=key)
        if resp.status_code == 404:
            return _not_found(f"https://www.shodan.io/host/{value}")
        resp.raise_for_status()
        d = resp.json()
        services = [
            {
                "port": s.get("port"),
                "transport": s.get("transport"),
                "product": s.get("product"),
                "version": s.get("version"),
                "module": (s.get("_shodan") or {}).get("module"),
                "timestamp": s.get("timestamp"),
                "banner": (s.get("data") or "")[:400],
            }
            for s in d.get("data") or []
        ]
        return Output(
            summary={
                "ports": sorted(d.get("ports") or []),
                "org": d.get("org"),
                "os": d.get("os"),
                "vulns": len(d.get("vulns") or []),
                "hostnames": d.get("hostnames"),
                "last_update": d.get("last_update"),
            },
            data={"services": services, "vulns": d.get("vulns"), "tags": d.get("tags")},
            source_url=f"https://www.shodan.io/host/{value}",
            pivots=[Pivot(InputType.DOMAIN, h, "Shodan hostname") for h in d.get("hostnames") or []],
        )


class Censys(Pipeline):
    name = "censys"
    label = "Censys"
    category = "threat-intel"
    accepts = frozenset({InputType.IP})
    key_fields = ("censys_api_token",)
    homepage = "https://platform.censys.io/"

    def enabled(self, settings: Settings) -> bool:
        # Platform personal access token, or the legacy Search API id + secret.
        return bool(settings.censys_api_token or (settings.censys_api_id and settings.censys_api_secret))

    async def run(self, target: Target, settings: Settings) -> Output:
        ip = query_value(target, self)
        if settings.censys_api_token:
            source = f"https://platform.censys.io/hosts/{ip}"
            resp = await http.get(
                f"https://api.platform.censys.io/v3/global/asset/host/{ip}",
                headers={"Authorization": f"Bearer {settings.censys_api_token}", "Accept": "application/json"},
            )
            if resp.status_code == 404:
                return _not_found(source)
            resp.raise_for_status()
            body = resp.json().get("result") or {}
            r = body.get("resource") or body
        else:
            source = f"https://search.censys.io/hosts/{ip}"
            resp = await http.get(
                f"https://search.censys.io/api/v2/hosts/{ip}",
                auth=(settings.censys_api_id, settings.censys_api_secret),
            )
            if resp.status_code == 404:
                return _not_found(source)
            resp.raise_for_status()
            r = resp.json().get("result") or {}
        services = [
            {
                "port": s.get("port"),
                "service": s.get("service_name") or s.get("protocol"),
                "transport": s.get("transport_protocol"),
                "software": [sw.get("product") for sw in s.get("software") or [] if isinstance(sw, dict)],
            }
            for s in r.get("services") or []
        ]
        asys = r.get("autonomous_system") or {}
        return Output(
            summary={
                "services": [f"{s['port']}/{s['service']}" for s in services],
                "asn": asys.get("asn"),
                "as_name": asys.get("name"),
                "os": (r.get("operating_system") or {}).get("product"),
                "last_updated": r.get("last_updated_at") or r.get("last_updated"),
            },
            data={"services": services, "location": r.get("location"), "dns": r.get("dns")},
            source_url=source,
        )


class VirusTotal(Pipeline):
    name = "virustotal"
    label = "VirusTotal"
    category = "threat-intel"
    accepts = frozenset({InputType.DOMAIN, InputType.IP, InputType.URL, InputType.HASH})
    key_fields = ("virustotal_api_key",)
    timeout_s = 45.0  # public API is throttled to 4 req/min
    homepage = "https://www.virustotal.com/"

    async def run(self, target: Target, settings: Settings) -> Output:
        kind = query_type(target, self)
        value = query_value(target, self)
        if kind == InputType.URL:
            vt_id = base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")
            path, gui = f"urls/{vt_id}", f"url/{vt_id}"
        else:
            path = {
                InputType.DOMAIN: f"domains/{value}",
                InputType.IP: f"ip_addresses/{value}",
                InputType.HASH: f"files/{value}",
            }[kind]
            gui = {InputType.DOMAIN: "domain", InputType.IP: "ip-address", InputType.HASH: "file"}[kind]
            gui = f"{gui}/{value}"
        source = f"https://www.virustotal.com/gui/{gui}"
        resp = await http.get(
            f"https://www.virustotal.com/api/v3/{path}", headers={"x-apikey": settings.virustotal_api_key}
        )
        if resp.status_code == 404:
            return _not_found(source)
        resp.raise_for_status()
        attrs = (resp.json().get("data") or {}).get("attributes") or {}
        stats = attrs.get("last_analysis_stats") or {}
        summary = {
            "malicious": stats.get("malicious"),
            "suspicious": stats.get("suspicious"),
            "harmless": stats.get("harmless"),
            "undetected": stats.get("undetected"),
            "reputation": attrs.get("reputation"),
            "tags": attrs.get("tags"),
        }
        if kind == InputType.HASH:
            summary.update(
                type=attrs.get("type_description"),
                size=attrs.get("size"),
                names=(attrs.get("names") or [])[:5],
                threat_label=(attrs.get("popular_threat_classification") or {}).get("suggested_threat_label"),
            )
        elif kind == InputType.DOMAIN:
            summary["categories"] = sorted(set((attrs.get("categories") or {}).values()))
        attrs.pop("last_analysis_results", None)
        return Output(summary=summary, data=attrs, source_url=source)


class AbuseIpDb(Pipeline):
    name = "abuseipdb"
    label = "AbuseIPDB"
    category = "threat-intel"
    accepts = frozenset({InputType.IP})
    key_fields = ("abuseipdb_api_key",)
    homepage = "https://www.abuseipdb.com/"

    async def run(self, target: Target, settings: Settings) -> Output:
        ip = query_value(target, self)
        d = await http.get_json(
            "https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": "90"},
            headers={"Key": settings.abuseipdb_api_key, "Accept": "application/json"},
        )
        d = d.get("data") or {}
        return Output(
            summary={
                "abuse_confidence": d.get("abuseConfidenceScore"),
                "reports_90d": d.get("totalReports"),
                "distinct_reporters": d.get("numDistinctUsers"),
                "usage_type": d.get("usageType"),
                "isp": d.get("isp"),
                "is_tor": d.get("isTor"),
                "last_reported": d.get("lastReportedAt"),
            },
            data=d,
            source_url=f"https://www.abuseipdb.com/check/{ip}",
        )


class GreyNoise(Pipeline):
    name = "greynoise"
    label = "GreyNoise"
    category = "threat-intel"
    accepts = frozenset({InputType.IP})
    key_fields = ("greynoise_api_key",)
    optional_key = True
    homepage = "https://viz.greynoise.io/"

    async def run(self, target: Target, settings: Settings) -> Output:
        ip = query_value(target, self)
        if ipaddress.ip_address(ip).version != 4:
            return Output(summary={"note": "GreyNoise community API covers IPv4 only"})
        headers = {"key": settings.greynoise_api_key} if settings.greynoise_api_key else {}
        resp = await http.get(f"https://api.greynoise.io/v3/community/{ip}", headers=headers)
        source = f"https://viz.greynoise.io/ip/{ip}"
        if resp.status_code == 404:
            return Output(summary={"seen_scanning": False, "riot": False}, data=resp.json(), source_url=source)
        resp.raise_for_status()
        d = resp.json()
        return Output(
            summary={
                "seen_scanning": d.get("noise"),
                "riot": d.get("riot"),  # known benign business service
                "classification": d.get("classification"),
                "name": d.get("name"),
                "last_seen": d.get("last_seen"),
            },
            data=d,
            source_url=source,
        )


class Otx(Pipeline):
    name = "otx"
    label = "AlienVault OTX"
    category = "threat-intel"
    accepts = frozenset({InputType.DOMAIN, InputType.IP, InputType.URL, InputType.HASH})
    key_fields = ("otx_api_key",)
    optional_key = True
    timeout_s = 30.0
    homepage = "https://otx.alienvault.com/"

    async def run(self, target: Target, settings: Settings) -> Output:
        kind = query_type(target, self)
        value = query_value(target, self)
        section = {
            InputType.DOMAIN: "domain",
            InputType.URL: "url",
            InputType.HASH: "file",
        }.get(kind) or ("IPv6" if ":" in value else "IPv4")
        headers = {"X-OTX-API-KEY": settings.otx_api_key} if settings.otx_api_key else {}
        resp = await http.get(
            f"https://otx.alienvault.com/api/v1/indicators/{section}/{value}/general", headers=headers
        )
        source = f"https://otx.alienvault.com/indicator/{section.lower()}/{value}"
        if resp.status_code in (400, 404):
            return _not_found(source)
        resp.raise_for_status()
        d = resp.json()
        pulse_info = d.get("pulse_info") or {}
        pulses = pulse_info.get("pulses") or []
        tags = sorted({t for p in pulses for t in p.get("tags") or []})
        return Output(
            summary={
                "pulse_count": pulse_info.get("count", 0),
                "recent_pulses": [p.get("name") for p in pulses[:5]],
                "malware_families": sorted(
                    {m.get("display_name") for p in pulses for m in p.get("malware_families") or []}
                )[:10],
                "tags": tags[:15],
            },
            data={
                "pulses": [
                    {k: p.get(k) for k in ("id", "name", "created", "modified", "tags", "adversary")}
                    for p in pulses[:50]
                ],
                "validation": d.get("validation"),
            },
            source_url=source,
        )


class UrlScan(Pipeline):
    name = "urlscan"
    label = "urlscan.io history"
    category = "threat-intel"
    accepts = frozenset({InputType.DOMAIN, InputType.IP, InputType.URL, InputType.HASH})
    key_fields = ("urlscan_api_key",)
    optional_key = True
    homepage = "https://urlscan.io/"

    async def run(self, target: Target, settings: Settings) -> Output:
        kind = query_type(target, self)
        value = query_value(target, self)
        q = {
            InputType.DOMAIN: f"domain:{value}",
            InputType.IP: f'ip:"{value}"',
            InputType.URL: f'page.url:"{value}"',
            InputType.HASH: f"hash:{value}",
        }[kind]
        headers = {"API-Key": settings.urlscan_api_key} if settings.urlscan_api_key else {}
        d = await http.get_json(
            "https://urlscan.io/api/v1/search/", params={"q": q, "size": "50"}, headers=headers
        )
        results = d.get("results") or []
        scans = [
            {
                "time": (r.get("task") or {}).get("time"),
                "url": (r.get("page") or {}).get("url"),
                "ip": (r.get("page") or {}).get("ip"),
                "server": (r.get("page") or {}).get("server"),
                "status": (r.get("page") or {}).get("status"),
                "malicious": (r.get("verdicts") or {}).get("malicious"),
                "result": r.get("result"),
                "screenshot": r.get("screenshot"),
            }
            for r in results
        ]
        ips = sorted({s["ip"] for s in scans if s["ip"]})
        return Output(
            summary={
                "total_scans": d.get("total"),
                "flagged_malicious": sum(1 for s in scans if s["malicious"]),
                "latest": scans[0]["time"] if scans else None,
                "distinct_ips": len(ips),
            },
            data={"scans": scans},
            source_url=f"https://urlscan.io/search/#{q}",
            pivots=[Pivot(InputType.IP, ip, "urlscan") for ip in ips[:30]] if kind != InputType.IP else [],
        )


class SecurityTrails(Pipeline):
    name = "securitytrails"
    label = "SecurityTrails"
    category = "dns"
    accepts = frozenset({InputType.DOMAIN})
    key_fields = ("securitytrails_api_key",)
    homepage = "https://securitytrails.com/"

    async def run(self, target: Target, settings: Settings) -> Output:
        domain = query_value(target, self)
        headers = {"APIKEY": settings.securitytrails_api_key}
        info = await http.get_json(f"https://api.securitytrails.com/v1/domain/{domain}", headers=headers)
        subs = await http.get_json(
            f"https://api.securitytrails.com/v1/domain/{domain}/subdomains", headers=headers
        )
        names = sorted(f"{s}.{domain}" for s in subs.get("subdomains") or [])
        return Output(
            summary={
                "subdomains": subs.get("subdomain_count", len(names)),
                "alexa_rank": info.get("alexa_rank"),
                "apex": info.get("apex_domain"),
            },
            data={"current_dns": info.get("current_dns"), "subdomains": names},
            source_url=f"https://securitytrails.com/domain/{domain}/dns",
            pivots=[Pivot(InputType.DOMAIN, n, "SecurityTrails") for n in names[:100]],
        )


class CirclHashlookup(Pipeline):
    name = "hashlookup"
    label = "CIRCL hashlookup (known files)"
    category = "threat-intel"
    accepts = frozenset({InputType.HASH})
    homepage = "https://hashlookup.circl.lu/"

    async def run(self, target: Target, settings: Settings) -> Output:
        algo = target.hash_algo
        if algo not in ("md5", "sha1", "sha256"):
            return Output(summary={"note": f"{algo} not supported by hashlookup"})
        url = f"https://hashlookup.circl.lu/lookup/{algo}/{target.value}"
        resp = await http.get(url)
        if resp.status_code == 404:
            return Output(summary={"known_file": False}, source_url=url)
        resp.raise_for_status()
        d = resp.json()
        return Output(
            summary={
                "known_file": True,
                "file_name": d.get("FileName"),
                "file_size": d.get("FileSize"),
                "source": d.get("source"),
                "trust": d.get("hashlookup:trust"),
                "known_malicious": d.get("KnownMalicious"),
            },
            data=d,
            source_url=url,
        )
