"""Every recon pipeline, in display order. Add new sources here."""

from app.recon.base import Pipeline
from app.recon.pipelines.certs import CrtSh, TlsCertificate
from app.recon.pipelines.dns_records import DnsRecords, ReverseDns, ZoneTransfer
from app.recon.pipelines.network import IpInfo, RipeStat
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
from app.recon.pipelines.web import HttpFingerprint, Wayback, WellKnown

ALL: list[Pipeline] = [
    Rdap(),
    DnsRecords(),
    ReverseDns(),
    ZoneTransfer(),
    CrtSh(),
    SecurityTrails(),
    RipeStat(),
    IpInfo(),
    TlsCertificate(),
    HttpFingerprint(),
    WellKnown(),
    Wayback(),
    Shodan(),
    Censys(),
    VirusTotal(),
    AbuseIpDb(),
    GreyNoise(),
    Otx(),
    UrlScan(),
    CirclHashlookup(),
]

BY_NAME: dict[str, Pipeline] = {p.name: p for p in ALL}
