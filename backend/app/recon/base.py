"""Pipeline contract shared by every recon source."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.recon.classify import InputType, Target


class SkipPipeline(Exception):
    """Raised by a pipeline that has nothing to do for this target (not an error)."""


@dataclass
class Pivot:
    type: str  # an InputType value
    value: str
    label: str = ""

    def as_dict(self) -> dict:
        return {"type": self.type, "value": self.value, "label": self.label}


@dataclass
class Output:
    summary: dict[str, Any]
    data: Any = None
    source_url: str | None = None
    pivots: list[Pivot] = field(default_factory=list)


class Pipeline(ABC):
    name: str  # stable id, e.g. "dns"
    label: str  # human name, e.g. "DNS records"
    category: str  # registration | dns | network | web | threat-intel | history
    accepts: frozenset[InputType]
    key_fields: tuple[str, ...] = ()  # Settings attributes that must be non-empty
    optional_key: bool = False  # works without the key, but better with it
    timeout_s: float | None = None  # overrides the global pipeline timeout
    homepage: str = ""

    def enabled(self, settings: Settings) -> bool:
        if self.optional_key:
            return True
        return all(getattr(settings, f) for f in self.key_fields)

    def applies_to(self, target: Target) -> bool:
        if target.type in self.accepts:
            return True
        # URL targets also run host-level pipelines against the URL's host.
        return target.type == InputType.URL and target.host_type in self.accepts

    @abstractmethod
    async def run(self, target: Target, settings: Settings) -> Output: ...

    def describe(self, settings: Settings) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "category": self.category,
            "accepts": sorted(t.value for t in self.accepts),
            "requires_key": bool(self.key_fields) and not self.optional_key,
            "optional_key": self.optional_key,
            "key_fields": list(self.key_fields),
            "enabled": self.enabled(settings),
            "homepage": self.homepage,
        }


def query_value(target: Target, pipeline: Pipeline) -> str:
    """What to send to a source: the URL itself if the pipeline takes URLs, else the host."""
    if target.type == InputType.URL and InputType.URL not in pipeline.accepts:
        return target.host or target.value
    return target.value


_tld = None


def registered_domain(host: str) -> str:
    """The registrable domain for a host (www.example.co.uk -> example.co.uk), using the
    public suffix list bundled with tldextract, so no network fetch is needed."""
    global _tld
    if _tld is None:
        import tldextract

        _tld = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
    parts = _tld(host)
    return parts.top_domain_under_public_suffix or host


def no_ipv6_route(host: str, exc: BaseException) -> bool:
    """True when a connection to an IPv6 literal failed because this machine has no IPv6 route."""
    if ":" not in host:
        return False
    text = f"{type(exc).__name__} {exc}".lower()
    return any(s in text for s in ("unreachable", "1231", "connecterror", "all connection attempts failed", "errno 101"))


def query_type(target: Target, pipeline: Pipeline) -> InputType:
    if target.type == InputType.URL and InputType.URL not in pipeline.accepts:
        return target.host_type  # type: ignore[return-value]
    return target.type
