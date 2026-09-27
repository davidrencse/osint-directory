"""DNS enumeration, reverse DNS and zone-transfer (AXFR) misconfiguration check."""

import asyncio

import dns.asyncresolver
import dns.exception
import dns.query
import dns.resolver
import dns.reversename
import dns.zone

from app.config import Settings
from app.recon.base import Output, Pipeline, Pivot, SkipPipeline, query_value, registered_domain
from app.recon.classify import InputType, Target

RECORD_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA", "DS")


def _resolver() -> dns.asyncresolver.Resolver:
    r = dns.asyncresolver.Resolver()
    r.lifetime = 6.0
    return r


async def _query(resolver, name: str, rtype: str) -> list[str]:
    try:
        answer = await resolver.resolve(name, rtype)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return []
    except dns.exception.Timeout:
        return ["<timeout>"]
    out = []
    for rr in answer:
        if rtype == "TXT":
            out.append(b"".join(rr.strings).decode(errors="replace"))
        else:
            out.append(rr.to_text())
    return out


class DnsRecords(Pipeline):
    name = "dns"
    label = "DNS records"
    category = "dns"
    accepts = frozenset({InputType.DOMAIN})

    async def run(self, target: Target, settings: Settings) -> Output:
        domain = query_value(target, self)
        resolver = _resolver()
        results = await asyncio.gather(*(_query(resolver, domain, t) for t in RECORD_TYPES))
        records = dict(zip(RECORD_TYPES, results))
        dmarc = [t for t in await _query(resolver, f"_dmarc.{domain}", "TXT") if t.startswith("v=DMARC")]
        spf = [t for t in records["TXT"] if t.lower().startswith("v=spf1")]

        mx_hosts = [m.split()[-1].rstrip(".") for m in records["MX"] if " " in m]
        null_mx = any(h == "" for h in mx_hosts)  # RFC 7505 "0 ." = domain accepts no mail
        mx_hosts = [h for h in mx_hosts if h]
        ns_hosts = [n.rstrip(".") for n in records["NS"]]
        ips = [ip for ip in records["A"] + records["AAAA"] if not ip.startswith("<")]

        email_security = {
            "spf": spf[0] if spf else None,
            "spf_all": (spf[0].split()[-1] if spf else None),
            "dmarc": dmarc[0] if dmarc else None,
            "dmarc_policy": next(
                (p.split("=", 1)[1] for p in (dmarc[0].split(";") if dmarc else []) if p.strip().startswith("p=")),
                None,
            ),
        }
        summary = {
            "A": records["A"],
            "AAAA": records["AAAA"],
            "MX": mx_hosts or ("null MX (no mail)" if null_mx else []),
            "NS": ns_hosts,
            "TXT_count": len(records["TXT"]),
            "CAA": records["CAA"],
            "dnssec_ds": bool(records["DS"]),
            "spf": email_security["spf"],
            "dmarc_policy": email_security["dmarc_policy"],
        }
        pivots = [Pivot(InputType.IP, ip, "resolves to") for ip in ips]
        pivots += [Pivot(InputType.DOMAIN, h, "mail server") for h in mx_hosts]
        return Output(
            summary=summary,
            data={"records": records, "email_security": email_security},
            pivots=pivots,
        )


class ReverseDns(Pipeline):
    name = "rdns"
    label = "Reverse DNS (PTR)"
    category = "dns"
    accepts = frozenset({InputType.IP})

    async def run(self, target: Target, settings: Settings) -> Output:
        ip = query_value(target, self)
        names = await _query(_resolver(), dns.reversename.from_address(ip).to_text(), "PTR")
        names = [n.rstrip(".") for n in names]
        return Output(
            summary={"ptr": names or None},
            data={"ptr": names},
            pivots=[Pivot(InputType.DOMAIN, n, "PTR") for n in names if not n.startswith("<")],
        )


def _try_axfr(ns_ip: str, domain: str) -> dict:
    try:
        zone = dns.zone.from_xfr(dns.query.xfr(ns_ip, domain, timeout=5, lifetime=10))
    except Exception as exc:  # refused, timeout, EOF, FormError... all mean "not allowed"
        return {"allowed": False, "reason": type(exc).__name__}
    names = sorted(str(n) for n in zone.nodes.keys())
    return {"allowed": True, "record_names": names[:500], "record_count": len(names)}


class ZoneTransfer(Pipeline):
    name = "axfr"
    label = "Zone transfer (AXFR) check"
    category = "dns"
    accepts = frozenset({InputType.DOMAIN})
    timeout_s = 40.0

    async def run(self, target: Target, settings: Settings) -> Output:
        domain = registered_domain(query_value(target, self))  # zones live at the apex
        resolver = _resolver()
        ns_hosts = [n.rstrip(".") for n in await _query(resolver, domain, "NS") if not n.startswith("<")]
        if not ns_hosts:
            raise SkipPipeline("No NS records")
        results = {}
        for ns in ns_hosts[:6]:
            addrs = await _query(resolver, ns, "A")
            if not addrs:
                results[ns] = {"allowed": False, "reason": "unresolvable"}
                continue
            results[ns] = await asyncio.to_thread(_try_axfr, addrs[0], domain)
        open_ns = [ns for ns, r in results.items() if r["allowed"]]
        return Output(
            summary={
                "zone": domain,
                "nameservers_tested": len(results),
                "vulnerable": bool(open_ns),
                "open_nameservers": open_ns,
            },
            data=results,
        )
