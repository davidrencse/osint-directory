"""Certificate transparency (crt.sh) and live TLS certificate inspection."""

import asyncio
import re
import ssl
from collections import Counter
from datetime import datetime, timezone

import httpx
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, NameOID

from app.config import Settings
from app.core import http
from app.recon.base import (
    Output,
    Pipeline,
    Pivot,
    SkipPipeline,
    no_ipv6_route,
    query_type,
    query_value,
    registered_domain,
)
from app.recon.classify import InputType, Target


class CrtSh(Pipeline):
    name = "crtsh"
    label = "Certificate transparency (crt.sh)"
    category = "dns"
    accepts = frozenset({InputType.DOMAIN})
    timeout_s = 60.0
    homepage = "https://crt.sh/"

    async def run(self, target: Target, settings: Settings) -> Output:
        # Certificates are issued at the registrable domain (often as wildcards), so search there.
        domain = registered_domain(query_value(target, self))
        try:
            certs = await self._crtsh(domain)
            source = f"https://crt.sh/?q=%25.{domain}"
        except Exception as crtsh_error:
            # crt.sh is often overloaded (404/502/timeouts); Cert Spotter covers the same logs.
            try:
                certs = await self._certspotter(domain)
            except Exception:
                raise crtsh_error from None
            source = "https://sslmate.com/certspotter/"
        names: set[str] = set()
        issuers: Counter[str] = Counter()
        for c in certs:
            for n in (c.get("name_value") or "").split("\n"):
                n = n.strip().lower().removeprefix("*.")
                if n == domain or n.endswith("." + domain):
                    names.add(n)
            issuers[_issuer_org(c.get("issuer_name", ""))] += 1
        subdomains = sorted(names)
        recent = sorted(certs, key=lambda c: c.get("not_before", ""), reverse=True)[:100]
        return Output(
            summary={
                "certificates": len(certs),
                "unique_names": len(subdomains),
                "top_issuers": dict(issuers.most_common(5)),
                "first_seen": min((c.get("not_before", "") for c in certs), default=None),
            },
            data={
                "subdomains": subdomains,
                "recent_certificates": [
                    {k: c.get(k) for k in ("id", "issuer_name", "name_value", "not_before", "not_after")}
                    for c in recent
                ],
            },
            source_url=source,
            pivots=[Pivot(InputType.DOMAIN, s, "CT log") for s in subdomains if s != domain][:150],
        )

    async def _crtsh(self, domain: str) -> list[dict]:
        # Unexpired certificates first: far smaller and faster for big domains.
        # crt.sh answers 404/5xx when busy, so try each form twice.
        last: Exception | None = None
        for query in (f"%25.{domain}&exclude=expired", f"%25.{domain}"):
            for attempt in range(2):
                try:
                    resp = await http.get(f"https://crt.sh/?q={query}&output=json", timeout=40.0, retries=0)
                    if resp.status_code == 200:
                        return resp.json()
                    last = httpx.HTTPStatusError(f"crt.sh {resp.status_code}", request=resp.request, response=resp)
                except (httpx.HTTPError, ValueError) as exc:
                    last = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        assert last is not None
        raise last

    async def _certspotter(self, domain: str) -> list[dict]:
        """Cert Spotter issuances, reshaped to the crt.sh fields used above."""
        rows = await http.get_json(
            "https://api.certspotter.com/v1/issuances",
            params={"domain": domain, "include_subdomains": "true", "expand": ["dns_names", "issuer"]},
            timeout=30.0,
        )
        return [
            {
                "id": r.get("id"),
                "issuer_name": f"O={(r.get('issuer') or {}).get('friendly_name') or (r.get('issuer') or {}).get('name', '')}",
                "name_value": "\n".join(r.get("dns_names") or []),
                "not_before": r.get("not_before", ""),
                "not_after": r.get("not_after", ""),
            }
            for r in rows
        ]


_ORG_RE = re.compile(r'(?:^|,\s*)O=("(?:[^"]|"")*"|[^,]*)')


def _issuer_org(issuer_name: str) -> str:
    m = _ORG_RE.search(issuer_name)
    if m:
        return m.group(1).strip('"')
    return issuer_name or "unknown"


def _name_attr(name: x509.Name, oid) -> str | None:
    attrs = name.get_attributes_for_oid(oid)
    return attrs[0].value if attrs else None


async def _handshake(host: str, sni: str | None, verify: bool):
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, 443, ssl=ctx, server_hostname=sni), timeout=10
    )
    try:
        sslobj = writer.get_extra_info("ssl_object")
        return sslobj.getpeercert(binary_form=True), sslobj.version(), sslobj.cipher()
    finally:
        writer.close()


class TlsCertificate(Pipeline):
    name = "tls"
    label = "TLS certificate"
    category = "web"
    accepts = frozenset({InputType.DOMAIN, InputType.IP})

    async def run(self, target: Target, settings: Settings) -> Output:
        host = query_value(target, self)
        sni = host if query_type(target, self) == InputType.DOMAIN else None
        try:
            der, version, cipher = await _handshake(host, sni, verify=False)
        except OSError as exc:
            if no_ipv6_route(host, exc):
                raise SkipPipeline("This machine has no IPv6 route, so the host can't be reached") from exc
            raise
        try:
            await _handshake(host, sni, verify=True)
            verified, verify_error = True, None
        except ssl.SSLCertVerificationError as exc:
            verified, verify_error = False, exc.verify_message
        except Exception as exc:
            verified, verify_error = False, str(exc)

        cert = x509.load_der_x509_certificate(der)
        try:
            sans = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            sans = []
        not_after = cert.not_valid_after_utc
        days_left = (not_after - datetime.now(timezone.utc)).days
        summary = {
            "subject_cn": _name_attr(cert.subject, NameOID.COMMON_NAME),
            "issuer": _name_attr(cert.issuer, NameOID.ORGANIZATION_NAME)
            or _name_attr(cert.issuer, NameOID.COMMON_NAME),
            "valid_from": cert.not_valid_before_utc.isoformat(),
            "valid_to": not_after.isoformat(),
            "days_left": days_left,
            "verified": verified,
            "verify_error": verify_error,
            "protocol": version,
            "cipher": cipher[0] if cipher else None,
            "san_count": len(sans),
        }
        data = {
            **summary,
            "serial": format(cert.serial_number, "x"),
            "signature_algorithm": cert.signature_hash_algorithm.name
            if cert.signature_hash_algorithm
            else None,
            "subject": cert.subject.rfc4514_string(),
            "issuer_dn": cert.issuer.rfc4514_string(),
            "sans": sans,
        }
        pivots = [
            Pivot(InputType.DOMAIN, s.removeprefix("*."), "SAN")
            for s in sans
            if s.removeprefix("*.") != host
        ][:100]
        return Output(summary=summary, data=data, pivots=pivots)
