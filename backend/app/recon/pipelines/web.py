"""HTTP fingerprinting, security-header grading, well-known files and Wayback history."""

import asyncio
import re

import httpx

from app.config import Settings
from app.core import http
from app.recon.base import Output, Pipeline, SkipPipeline, no_ipv6_route, query_type, query_value
from app.recon.classify import InputType, Target

MAX_BODY = 512 * 1024

# header -> (weight, advice)
SECURITY_HEADERS = {
    "strict-transport-security": (20, "Enforce HTTPS with HSTS"),
    "content-security-policy": (25, "Define a Content-Security-Policy"),
    "x-frame-options": (10, "Prevent clickjacking (or use CSP frame-ancestors)"),
    "x-content-type-options": (10, "Set nosniff"),
    "referrer-policy": (10, "Limit referrer leakage"),
    "permissions-policy": (10, "Restrict powerful browser features"),
    "cross-origin-opener-policy": (5, "Isolate browsing context"),
    "cross-origin-resource-policy": (5, "Restrict cross-origin reads"),
    "cross-origin-embedder-policy": (5, "Require CORP/CORS for subresources"),
}
FINGERPRINT_HEADERS = ("server", "x-powered-by", "x-aspnet-version", "x-generator", "via", "x-cache", "cf-ray")
_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
_GENERATOR_RE = re.compile(rb'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', re.I)


def _grade(score: int) -> str:
    for threshold, letter in ((90, "A"), (75, "B"), (55, "C"), (35, "D"), (15, "E")):
        if score >= threshold:
            return letter
    return "F"


async def _fetch_capped(url: str) -> tuple[httpx.Response, bytes]:
    async with http.client().stream("GET", url, timeout=15.0) as resp:
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk
            if len(body) >= MAX_BODY:
                break
        return resp, body


class HttpFingerprint(Pipeline):
    name = "http"
    label = "HTTP fingerprint & security headers"
    category = "web"
    accepts = frozenset({InputType.DOMAIN, InputType.IP, InputType.URL})

    async def run(self, target: Target, settings: Settings) -> Output:
        if query_type(target, self) == InputType.URL:
            candidates = [target.value]
        else:
            host = query_value(target, self)
            host = f"[{host}]" if ":" in host else host
            candidates = [f"https://{host}/", f"http://{host}/"]

        last_error: Exception | None = None
        for url in candidates:
            try:
                resp, body = await _fetch_capped(url)
                break
            except httpx.HTTPError as exc:
                last_error = exc
        else:
            if last_error is not None and no_ipv6_route(target.host or "", last_error):
                raise SkipPipeline("This machine has no IPv6 route, so the host can't be reached")
            raise RuntimeError(f"No HTTP response: {last_error}")

        headers = {k.lower(): v for k, v in resp.headers.items()}
        score = 0
        missing = []
        for h, (weight, advice) in SECURITY_HEADERS.items():
            if h in headers:
                score += weight
            else:
                missing.append({"header": h, "advice": advice})
        title = _TITLE_RE.search(body)
        generator = _GENERATOR_RE.search(body)
        chain = [{"status": r.status_code, "url": str(r.url)} for r in resp.history]
        cookies = [
            {
                "name": c.split("=", 1)[0],
                "secure": "secure" in c.lower(),
                "httponly": "httponly" in c.lower(),
                "samesite": next((p.split("=")[1] for p in c.split(";") if "samesite" in p.lower()), None),
            }
            for c in resp.headers.get_list("set-cookie")
        ]
        summary = {
            "status": resp.status_code,
            "final_url": str(resp.url),
            "title": title.group(1).decode(errors="replace").strip()[:200] if title else None,
            "server": headers.get("server"),
            "powered_by": headers.get("x-powered-by"),
            "generator": generator.group(1).decode(errors="replace") if generator else None,
            "security_grade": _grade(score),
            "security_score": score,
            "redirects": len(chain),
        }
        return Output(
            summary=summary,
            data={
                "redirect_chain": chain,
                "headers": headers,
                "fingerprint": {h: headers[h] for h in FINGERPRINT_HEADERS if h in headers},
                "missing_security_headers": missing,
                "cookies": cookies,
                "body_bytes_read": len(body),
            },
            source_url=str(resp.url),
        )


class WellKnown(Pipeline):
    name = "wellknown"
    label = "robots.txt & security.txt"
    category = "web"
    accepts = frozenset({InputType.DOMAIN})

    async def run(self, target: Target, settings: Settings) -> Output:
        domain = query_value(target, self)

        async def fetch(path: str) -> str | None:
            try:
                resp = await http.get(f"https://{domain}{path}", timeout=10.0, retries=0)
            except httpx.HTTPError:
                return None
            ctype = resp.headers.get("content-type", "")
            if resp.status_code != 200 or "html" in ctype:
                return None
            return resp.text[:100_000]

        robots, sectxt = await asyncio.gather(fetch("/robots.txt"), fetch("/.well-known/security.txt"))
        if robots is None and sectxt is None:
            return Output(summary={"robots_txt": False, "security_txt": False})

        disallow, sitemaps = [], []
        for line in (robots or "").splitlines():
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "disallow" and val and val not in disallow:
                disallow.append(val)
            elif key == "sitemap":
                sitemaps.append(val)

        sec_fields: dict[str, list[str]] = {}
        for line in (sectxt or "").splitlines():
            if ":" in line and not line.startswith("#"):
                k, _, v = line.partition(":")
                sec_fields.setdefault(k.strip(), []).append(v.strip())

        return Output(
            summary={
                "robots_txt": robots is not None,
                "disallowed_paths": len(disallow),
                "sitemaps": sitemaps[:5],
                "security_txt": sectxt is not None,
                "security_contact": (sec_fields.get("Contact") or [None])[0],
            },
            data={"disallow": disallow[:300], "sitemaps": sitemaps, "security_txt": sec_fields, "robots_raw": robots},
            source_url=f"https://{domain}/robots.txt",
        )


class Wayback(Pipeline):
    name = "wayback"
    label = "Wayback Machine history"
    category = "history"
    accepts = frozenset({InputType.DOMAIN, InputType.URL})
    timeout_s = 40.0
    homepage = "https://web.archive.org/"

    async def run(self, target: Target, settings: Settings) -> Output:
        value = query_value(target, self)
        cdx = "https://web.archive.org/cdx/search/cdx"
        # One row per year keeps the CDX query light enough for popular domains.
        yearly_params = {"url": value, "output": "json", "fl": "timestamp,statuscode", "collapse": "timestamp:4", "limit": "100"}
        urls_params = {"url": value, "output": "json", "fl": "original,mimetype,statuscode", "collapse": "urlkey", "limit": "150"}
        if query_type(target, self) == InputType.DOMAIN:
            urls_params["matchType"] = "domain"

        async def snapshot(timestamp: str | None) -> dict | None:
            # The availability API is fast even when CDX is overloaded.
            params = {"url": value, **({"timestamp": timestamp} if timestamp else {})}
            body = await http.get_json("https://archive.org/wayback/available", params=params, timeout=20.0, retries=1)
            return (body.get("archived_snapshots") or {}).get("closest")

        yearly, urls, earliest, latest = await asyncio.gather(
            http.get_json(cdx, params=yearly_params, timeout=25.0, retries=0),
            http.get_json(cdx, params=urls_params, timeout=25.0, retries=0),
            snapshot("19960101"),
            snapshot(None),
            return_exceptions=True,
        )
        years = yearly[1:] if isinstance(yearly, list) else []
        url_rows = urls[1:] if isinstance(urls, list) else []
        first = earliest if isinstance(earliest, dict) else None
        last = latest if isinstance(latest, dict) else None
        if not (years or url_rows or first or last):
            errors = [r for r in (yearly, urls, earliest, latest) if isinstance(r, Exception)]
            if errors:
                raise errors[0]
            raise SkipPipeline("No archived captures")

        partial = [f"{name}: {type(r).__name__}" for name, r in (("history", yearly), ("urls", urls)) if isinstance(r, Exception)]
        return Output(
            summary={
                "first_capture": years[0][0] if years else (first or {}).get("timestamp"),
                "last_capture": (last or {}).get("timestamp") or (years[-1][0] if years else None),
                "years_with_captures": len(years) if years else None,
                "unique_urls_sampled": len(url_rows) if url_rows else None,
                "note": "The archive's history search was slow, so only the first and latest snapshots are shown" if partial else None,
            },
            data={
                "partial_errors": partial,
                "years": [ts[:4] for ts, _ in years],
                "latest_snapshot": (last or {}).get("url"),
                "earliest_snapshot": (first or {}).get("url"),
                "urls": [{"url": u, "mime": m, "status": st} for u, m, st in url_rows],
            },
            source_url=f"https://web.archive.org/web/*/{value}*",
        )
