import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

router = APIRouter(prefix="/api/tools", tags=["tools"])

CATALOG = Path(__file__).resolve().parent / "catalog.json"

# External tools that accept an infrastructure indicator in the URL. Only these get prefilled
# links; the rest of the catalog is link-out only.
QUICK_LINKS = {
    "domain": [
        ("crt.sh", "https://crt.sh/?q=%25.{v}"),
        ("DNSDumpster", "https://dnsdumpster.com/"),
        ("SecurityTrails", "https://securitytrails.com/domain/{v}/dns"),
        ("VirusTotal", "https://www.virustotal.com/gui/domain/{v}"),
        ("urlscan.io", "https://urlscan.io/search/#domain:{v}"),
        ("Shodan", "https://www.shodan.io/search?query=hostname%3A{v}"),
        ("Censys", "https://search.censys.io/search?resource=hosts&q={v}"),
        ("ViewDNS", "https://viewdns.info/iphistory/?domain={v}"),
        ("Wayback Machine", "https://web.archive.org/web/*/{v}*"),
        ("BuiltWith", "https://builtwith.com/{v}"),
        ("MXToolbox", "https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{v}"),
        ("SSL Labs", "https://www.ssllabs.com/ssltest/analyze.html?d={v}"),
        ("Security Headers", "https://securityheaders.com/?q={v}&followRedirects=on"),
        ("AlienVault OTX", "https://otx.alienvault.com/indicator/domain/{v}"),
    ],
    "ip": [
        ("Shodan", "https://www.shodan.io/host/{v}"),
        ("Censys", "https://search.censys.io/hosts/{v}"),
        ("GreyNoise", "https://viz.greynoise.io/ip/{v}"),
        ("AbuseIPDB", "https://www.abuseipdb.com/check/{v}"),
        ("VirusTotal", "https://www.virustotal.com/gui/ip-address/{v}"),
        ("bgp.he.net", "https://bgp.he.net/ip/{v}"),
        ("ipinfo", "https://ipinfo.io/{v}"),
        ("urlscan.io", "https://urlscan.io/search/#ip:%22{v}%22"),
        ("AlienVault OTX", "https://otx.alienvault.com/indicator/ip/{v}"),
        ("Talos", "https://talosintelligence.com/reputation_center/lookup?search={v}"),
    ],
    "asn": [
        ("bgp.he.net", "https://bgp.he.net/{v}"),
        ("RIPEstat", "https://stat.ripe.net/{v}"),
        ("PeeringDB", "https://www.peeringdb.com/search?q={n}"),
        ("BGPView", "https://bgpview.io/asn/{n}"),
    ],
    "cidr": [
        ("bgp.he.net", "https://bgp.he.net/net/{v}"),
        ("RIPEstat", "https://stat.ripe.net/{v}"),
        ("Shodan", "https://www.shodan.io/search?query=net%3A{v}"),
    ],
    "hash": [
        ("VirusTotal", "https://www.virustotal.com/gui/file/{v}"),
        ("MalwareBazaar", "https://bazaar.abuse.ch/browse.php?search=sha256%3A{v}"),
        ("Hybrid Analysis", "https://www.hybrid-analysis.com/search?query={v}"),
        ("CIRCL hashlookup", "https://hashlookup.circl.lu/lookup/sha256/{v}"),
        ("AlienVault OTX", "https://otx.alienvault.com/indicator/file/{v}"),
    ],
    "url": [
        ("urlscan.io", "https://urlscan.io/search/#page.url:%22{v}%22"),
        ("Wayback Machine", "https://web.archive.org/web/*/{v}"),
        ("Google Safe Browsing", "https://transparencyreport.google.com/safe-browsing/search?url={v}"),
    ],
}


@lru_cache
def _catalog_bytes() -> bytes:
    """The catalog as compact JSON, built once. Letting FastAPI re-encode ~1,500 tools per request is slow."""
    if not CATALOG.exists():
        raise HTTPException(503, "Tool catalog not built. Run: uv run python scripts/build_catalog.py")
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@router.get("/catalog")
def catalog():
    return Response(_catalog_bytes(), media_type="application/json")


@router.get("/quick-links")
def quick_links():
    return {kind: [{"name": n, "template": t} for n, t in links] for kind, links in QUICK_LINKS.items()}
