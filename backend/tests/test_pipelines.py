"""Every pipeline's request shape and parsing, with HTTP mocked (no keys or network needed)."""

import base64

import httpx
import pytest
import respx

from app.config import Settings
from app.recon.base import SkipPipeline, no_ipv6_route, registered_domain
from app.recon.classify import classify
from app.recon.pipelines.certs import CrtSh
from app.recon.pipelines.registration import Rdap
from app.recon.pipelines.threatintel import (
    AbuseIpDb,
    Censys,
    CirclHashlookup,
    GreyNoise,
    Otx,
    SecurityTrails,
    Shodan,
    UrlScan,
    VirusTotal,
)
from app.recon.pipelines.web import Wayback

KEYS = Settings(
    _env_file=None,
    shodan_api_key="k",
    censys_api_token="tok",
    virustotal_api_key="k",
    abuseipdb_api_key="k",
    securitytrails_api_key="k",
    greynoise_api_key="k",
)


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    async def instant(*_):
        return None

    monkeypatch.setattr("asyncio.sleep", instant)


# --- helpers ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host,apex",
    [("www.wikipedia.org", "wikipedia.org"), ("a.b.example.co.uk", "example.co.uk"), ("example.com", "example.com")],
)
def test_registered_domain(host, apex):
    assert registered_domain(host) == apex


def test_no_ipv6_route():
    assert no_ipv6_route("2606:4700::1111", OSError("[WinError 1231] The network location cannot be reached"))
    assert not no_ipv6_route("1.1.1.1", OSError("unreachable"))


# --- keyless fallbacks -----------------------------------------------------------------------


@respx.mock
async def test_rdap_uses_registered_domain_for_subdomains():
    route = respx.get("https://rdap.org/domain/wikipedia.org").mock(return_value=httpx.Response(200, json={}))
    out = await Rdap().run(classify("https://www.wikipedia.org/wiki/x"), Settings(_env_file=None))
    assert route.called and out.summary["domain"] == "wikipedia.org"


@respx.mock
async def test_crtsh_falls_back_to_certspotter():
    respx.get(url__startswith="https://crt.sh/").mock(return_value=httpx.Response(502))
    respx.get(url__startswith="https://api.certspotter.com/v1/issuances").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "1",
                    "dns_names": ["example.com", "*.api.example.com", "other.net"],
                    "issuer": {"friendly_name": "Let's Encrypt"},
                    "not_before": "2026-01-01T00:00:00Z",
                    "not_after": "2026-04-01T00:00:00Z",
                }
            ],
        )
    )
    out = await CrtSh().run(classify("example.com"), Settings(_env_file=None))
    assert out.data["subdomains"] == ["api.example.com", "example.com"]
    assert out.summary["top_issuers"] == {"Let's Encrypt": 1}
    assert "certspotter" in out.source_url


@respx.mock
async def test_crtsh_prefers_unexpired_query():
    route = respx.get(url__regex=r"https://crt\.sh/\?q=%25\.example\.com&exclude=expired.*").mock(
        return_value=httpx.Response(200, json=[{"name_value": "www.example.com", "issuer_name": "C=US, O=\"DigiCert, Inc.\""}])
    )
    out = await CrtSh().run(classify("example.com"), Settings(_env_file=None))
    assert route.called
    assert out.summary["top_issuers"] == {"DigiCert, Inc.": 1}


@respx.mock
async def test_wayback_survives_cdx_outage():
    respx.get(url__startswith="https://web.archive.org/cdx/").mock(return_value=httpx.Response(504))
    respx.get(url__startswith="https://archive.org/wayback/available").mock(
        return_value=httpx.Response(
            200,
            json={"archived_snapshots": {"closest": {"timestamp": "20260926131742", "url": "http://web.archive.org/web/x"}}},
        )
    )
    out = await Wayback().run(classify("wikipedia.org"), Settings(_env_file=None))
    assert out.summary["last_capture"] == "20260926131742"
    assert out.summary["note"]


@respx.mock
async def test_wayback_nothing_archived_is_skipped():
    respx.get(url__startswith="https://web.archive.org/cdx/").mock(return_value=httpx.Response(200, json=[]))
    respx.get(url__startswith="https://archive.org/wayback/available").mock(
        return_value=httpx.Response(200, json={"archived_snapshots": {}})
    )
    with pytest.raises(SkipPipeline):
        await Wayback().run(classify("never-archived.example"), Settings(_env_file=None))


# --- keyed sources ---------------------------------------------------------------------------


@respx.mock
async def test_shodan_host():
    respx.get("https://api.shodan.io/shodan/host/8.8.8.8", params={"key": "k"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "ports": [443, 53],
                "org": "Google",
                "hostnames": ["dns.google"],
                "vulns": ["CVE-1"],
                "data": [{"port": 53, "transport": "udp", "product": "Google DNS", "data": "x" * 900, "_shodan": {"module": "dns"}}],
            },
        )
    )
    out = await Shodan().run(classify("8.8.8.8"), KEYS)
    assert out.summary["ports"] == [53, 443]
    assert out.summary["vulns"] == 1
    assert len(out.data["services"][0]["banner"]) == 400
    assert out.pivots[0].value == "dns.google"


@respx.mock
async def test_shodan_domain():
    respx.get("https://api.shodan.io/dns/domain/example.com").mock(
        return_value=httpx.Response(200, json={"subdomains": ["www", "mail"], "tags": ["ipv6"]})
    )
    out = await Shodan().run(classify("example.com"), KEYS)
    assert out.summary["subdomains"] == 2
    assert {p.value for p in out.pivots} == {"www.example.com", "mail.example.com"}


def test_censys_enabled_by_token_or_legacy_pair():
    assert Censys().enabled(Settings(_env_file=None, censys_api_token="t"))
    assert Censys().enabled(Settings(_env_file=None, censys_api_id="i", censys_api_secret="s"))
    assert not Censys().enabled(Settings(_env_file=None, censys_api_id="i"))


@respx.mock
async def test_censys_platform_token():
    route = respx.get("https://api.platform.censys.io/v3/global/asset/host/1.1.1.1").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "resource": {
                        "services": [{"port": 443, "protocol": "HTTP", "transport_protocol": "tcp"}],
                        "autonomous_system": {"asn": 13335, "name": "CLOUDFLARENET"},
                    }
                }
            },
        )
    )
    out = await Censys().run(classify("1.1.1.1"), KEYS)
    assert route.calls.last.request.headers["authorization"] == "Bearer tok"
    assert out.summary["services"] == ["443/HTTP"] and out.summary["asn"] == 13335


@respx.mock
async def test_censys_legacy_pair():
    respx.get("https://search.censys.io/api/v2/hosts/1.1.1.1").mock(
        return_value=httpx.Response(200, json={"result": {"services": [{"port": 80, "service_name": "HTTP"}]}})
    )
    out = await Censys().run(classify("1.1.1.1"), Settings(_env_file=None, censys_api_id="i", censys_api_secret="s"))
    assert out.summary["services"] == ["80/HTTP"]


@respx.mock
@pytest.mark.parametrize(
    "target,path",
    [
        ("example.com", "domains/example.com"),
        ("8.8.8.8", "ip_addresses/8.8.8.8"),
        ("44d88612fea8a8f36de82e1278abb02f", "files/44d88612fea8a8f36de82e1278abb02f"),
        ("https://example.com/a", "urls/" + base64.urlsafe_b64encode(b"https://example.com/a").decode().rstrip("=")),
    ],
)
async def test_virustotal_paths(target, path):
    route = respx.get(f"https://www.virustotal.com/api/v3/{path}").mock(
        return_value=httpx.Response(
            200, json={"data": {"attributes": {"last_analysis_stats": {"malicious": 3}, "last_analysis_results": {"x": 1}}}}
        )
    )
    out = await VirusTotal().run(classify(target), KEYS)
    assert route.calls.last.request.headers["x-apikey"] == "k"
    assert out.summary["malicious"] == 3
    assert "last_analysis_results" not in out.data


@respx.mock
async def test_virustotal_not_found():
    respx.get(url__startswith="https://www.virustotal.com/").mock(return_value=httpx.Response(404))
    out = await VirusTotal().run(classify("example.com"), KEYS)
    assert out.summary == {"found": False}


@respx.mock
async def test_abuseipdb():
    respx.get(url__startswith="https://api.abuseipdb.com/api/v2/check").mock(
        return_value=httpx.Response(200, json={"data": {"abuseConfidenceScore": 87, "totalReports": 12, "isTor": False}})
    )
    out = await AbuseIpDb().run(classify("192.0.2.1"), KEYS)
    assert out.summary["abuse_confidence"] == 87


@respx.mock
async def test_greynoise_key_header_and_unseen():
    route = respx.get("https://api.greynoise.io/v3/community/192.0.2.1").mock(
        return_value=httpx.Response(404, json={"message": "IP not observed"})
    )
    out = await GreyNoise().run(classify("192.0.2.1"), KEYS)
    assert route.calls.last.request.headers["key"] == "k"
    assert out.summary["seen_scanning"] is False


@respx.mock
async def test_securitytrails():
    respx.get("https://api.securitytrails.com/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={"apex_domain": "example.com"})
    )
    respx.get("https://api.securitytrails.com/v1/domain/example.com/subdomains").mock(
        return_value=httpx.Response(200, json={"subdomains": ["www", "api"], "subdomain_count": 2})
    )
    out = await SecurityTrails().run(classify("example.com"), KEYS)
    assert out.summary["subdomains"] == 2
    assert out.data["subdomains"] == ["api.example.com", "www.example.com"]


@respx.mock
async def test_otx_and_urlscan_and_hashlookup():
    respx.get("https://otx.alienvault.com/api/v1/indicators/IPv4/8.8.8.8/general").mock(
        return_value=httpx.Response(200, json={"pulse_info": {"count": 1, "pulses": [{"name": "p", "tags": ["dns"]}]}})
    )
    respx.get(url__startswith="https://urlscan.io/api/v1/search/").mock(
        return_value=httpx.Response(200, json={"total": 1, "results": [{"page": {"url": "https://x", "ip": "192.0.2.9"}}]})
    )
    respx.get(url__startswith="https://hashlookup.circl.lu/").mock(return_value=httpx.Response(404))
    s = Settings(_env_file=None)
    assert (await Otx().run(classify("8.8.8.8"), s)).summary["pulse_count"] == 1
    assert (await UrlScan().run(classify("example.com"), s)).pivots[0].value == "192.0.2.9"
    assert (await CirclHashlookup().run(classify("a" * 32), s)).summary == {"known_file": False}
