"""Optional allowlist: when non-empty, recon only runs against targets inside it."""

import ipaddress

from app.recon.classify import InputType, Target, is_ip


def _host_in_entry(host: str, entry: str) -> bool:
    if is_ip(host):
        try:
            return ipaddress.ip_address(host) in ipaddress.ip_network(entry, strict=False)
        except ValueError:
            return False
    entry = entry.removeprefix("*.")
    return host == entry or host.endswith("." + entry)


def in_scope(target: Target, entries: list[str]) -> bool:
    if not entries:
        return True
    if target.type == InputType.HASH:
        return True  # file hashes aren't infrastructure; nothing to scope
    if target.type == InputType.ASN:
        return target.value.lower() in entries
    if target.type == InputType.CIDR:
        net = ipaddress.ip_network(target.value)
        for e in entries:
            try:
                if net.subnet_of(ipaddress.ip_network(e, strict=False)):  # type: ignore[arg-type]
                    return True
            except (ValueError, TypeError):
                continue
        return False
    host = (target.host or target.value).lower()
    return any(_host_in_entry(host, e) for e in entries)
