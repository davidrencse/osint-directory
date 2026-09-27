"""RDAP (the structured successor to WHOIS) for domains, IP allocations and ASNs."""

from app.config import Settings
from app.core import http
from app.recon.base import Output, Pipeline, Pivot, query_type, query_value, registered_domain
from app.recon.classify import InputType, Target


def _vcard_fn(entity: dict) -> str | None:
    for item in (entity.get("vcardArray") or [None, []])[1]:
        if item and item[0] == "fn":
            return item[3]
    return None


def _entities_by_role(entities: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    stack = list(entities or [])
    while stack:
        ent = stack.pop()
        name = _vcard_fn(ent) or ent.get("handle")
        for role in ent.get("roles") or []:
            if name and name not in out.setdefault(role, []):
                out[role].append(name)
        stack.extend(ent.get("entities") or [])
    return out


def _events(obj: dict) -> dict[str, str]:
    return {e["eventAction"]: e.get("eventDate", "") for e in obj.get("events") or []}


class Rdap(Pipeline):
    name = "rdap"
    label = "RDAP / WHOIS"
    category = "registration"
    accepts = frozenset({InputType.DOMAIN, InputType.IP, InputType.ASN, InputType.CIDR})
    homepage = "https://about.rdap.org/"

    async def run(self, target: Target, settings: Settings) -> Output:
        kind = query_type(target, self)
        value = query_value(target, self)
        if kind == InputType.DOMAIN:
            value = registered_domain(value)  # registries only know the registrable name
        path = {
            InputType.DOMAIN: f"domain/{value}",
            InputType.IP: f"ip/{value}",
            InputType.CIDR: f"ip/{value}",
            InputType.ASN: f"autnum/{value.removeprefix('AS')}",
        }[kind]
        url = f"https://rdap.org/{path}"
        resp = await http.get(url, headers={"Accept": "application/rdap+json"})
        if resp.status_code == 404:
            return Output(summary={"found": False}, source_url=url)
        resp.raise_for_status()
        data = resp.json()
        roles = _entities_by_role(data.get("entities") or [])
        events = _events(data)
        pivots: list[Pivot] = []

        if kind == InputType.DOMAIN:
            nameservers = [ns.get("ldhName", "").lower() for ns in data.get("nameservers") or []]
            summary = {
                "domain": value,
                "registrar": (roles.get("registrar") or [None])[0],
                "registered": events.get("registration"),
                "expires": events.get("expiration"),
                "updated": events.get("last changed"),
                "status": data.get("status"),
                "nameservers": nameservers,
                "dnssec": (data.get("secureDNS") or {}).get("delegationSigned"),
            }
        elif kind == InputType.ASN:
            summary = {
                "asn": f"AS{data.get('startAutnum')}",
                "name": data.get("name"),
                "country": data.get("country"),
                "registrant": (roles.get("registrant") or [None])[0],
                "registered": events.get("registration"),
                "updated": events.get("last changed"),
            }
        else:
            cidrs = [
                f"{c.get('v4prefix') or c.get('v6prefix')}/{c.get('length')}"
                for c in data.get("cidr0_cidrs") or []
            ]
            summary = {
                "network": data.get("name"),
                "handle": data.get("handle"),
                "range": f"{data.get('startAddress')} - {data.get('endAddress')}",
                "cidrs": cidrs,
                "country": data.get("country"),
                "registrant": (roles.get("registrant") or [None])[0],
                "abuse": (roles.get("abuse") or [None])[0],
                "registered": events.get("registration"),
            }
            pivots = [Pivot(InputType.CIDR, c, "allocation") for c in cidrs if "None" not in c]
        return Output(summary=summary, data=data, source_url=str(resp.url), pivots=pivots)
