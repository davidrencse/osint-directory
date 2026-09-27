"""Detect what kind of infrastructure indicator a user typed."""

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit


class InputType(StrEnum):
    DOMAIN = "domain"
    IP = "ip"
    CIDR = "cidr"
    ASN = "asn"
    URL = "url"
    HASH = "hash"


_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}[a-z0-9]$"
)
_ASN_RE = re.compile(r"^as(\d{1,10})$")
_HASH_LENGTHS = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
_HEX_RE = re.compile(r"^[a-f0-9]+$")


class ClassifyError(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    raw: str
    type: InputType
    value: str  # normalised indicator
    host: str | None = None  # the domain or IP a DOMAIN/IP/URL target points at
    hash_algo: str | None = None

    @property
    def host_type(self) -> InputType | None:
        if self.type in (InputType.DOMAIN, InputType.IP):
            return self.type
        if self.host is None:
            return None
        return InputType.IP if is_ip(self.host) else InputType.DOMAIN

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "type": self.type.value,
            "value": self.value,
            "host": self.host,
            "hash_algo": self.hash_algo,
        }


def is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def classify(raw: str) -> Target:
    s = raw.strip()
    if not s:
        raise ClassifyError("Empty input")
    low = s.lower()

    if "@" in low:
        raise ClassifyError(
            "Email addresses are out of scope. This dashboard does infrastructure recon only."
        )

    if re.match(r"^[a-z][a-z0-9+.-]*://", low):
        host = (urlsplit(s).hostname or "").lower()
        if not host:
            raise ClassifyError("URL has no host")
        if not (is_ip(host) or _DOMAIN_RE.match(host)):
            raise ClassifyError(f"URL host '{host}' is not a valid domain or IP")
        return Target(raw=s, type=InputType.URL, value=s, host=host)

    bare = low.strip("[]")
    if is_ip(bare):
        ip = str(ipaddress.ip_address(bare))
        return Target(raw=s, type=InputType.IP, value=ip, host=ip)

    if "/" in low:
        try:
            net = ipaddress.ip_network(low, strict=False)
        except ValueError as exc:
            raise ClassifyError(f"Invalid CIDR: {exc}") from exc
        return Target(raw=s, type=InputType.CIDR, value=str(net))

    m = _ASN_RE.match(low.replace(" ", ""))
    if m:
        return Target(raw=s, type=InputType.ASN, value=f"AS{int(m.group(1))}")

    if _HEX_RE.match(low) and len(low) in _HASH_LENGTHS:
        return Target(raw=s, type=InputType.HASH, value=low, hash_algo=_HASH_LENGTHS[len(low)])

    domain = low.rstrip(".")
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    if _DOMAIN_RE.match(domain):
        return Target(raw=s, type=InputType.DOMAIN, value=domain, host=domain)

    raise ClassifyError(
        "Could not classify input. Expected a domain, IP, CIDR, ASN (e.g. AS15169), URL or file hash."
    )
