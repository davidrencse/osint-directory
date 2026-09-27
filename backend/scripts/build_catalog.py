"""Build app/tools/catalog.json from OSINT Framework (MIT) and OSINT Directory.

    uv run python scripts/build_catalog.py

The launcher only links out to tools; nothing here queries a tool on the user's behalf.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

OUT = Path(__file__).resolve().parent.parent / "app" / "tools" / "catalog.json"
ARF_URL = "https://raw.githubusercontent.com/lockfale/OSINT-Framework/master/public/arf.json"
OSINTDIR_URL = "https://www.osintdirectory.com/tools"
UA = "Mozilla/5.0 (osint-dashboard catalog builder)"


def _norm_url(u: str) -> str:
    p = urlsplit(u.strip())
    return f"{(p.hostname or '').removeprefix('www.')}{p.path.rstrip('/')}".lower()


def from_osint_framework(client: httpx.Client) -> list[dict]:
    root = client.get(ARF_URL).raise_for_status().json()
    tools: list[dict] = []

    def walk(node: dict, path: list[str]) -> None:
        if node.get("type") == "url":
            name = node["name"]
            flags = re.findall(r"\(([TDRM])\)", name)
            tools.append(
                {
                    "name": re.sub(r"\s*\([TDRM]\)", "", name).strip(),
                    "url": node["url"],
                    "category": path[0] if path else "Other",
                    "path": path,
                    "description": node.get("description") or "",
                    "pricing": node.get("pricing") or "unknown",
                    "input": node.get("input"),
                    "output": node.get("output"),
                    "opsec": node.get("opsec"),
                    "opsec_note": node.get("opsecNote"),
                    "local_install": bool(node.get("localInstall") or "T" in flags),
                    "google_dork": bool(node.get("googleDork") or "D" in flags),
                    "registration": bool(node.get("registration") or "R" in flags),
                    "manual_url_edit": bool(node.get("editUrl") or "M" in flags),
                    "api": bool(node.get("api")),
                    "deprecated": bool(node.get("deprecated")) or node.get("status") == "dead",
                    "sources": ["osintframework"],
                }
            )
        for child in node.get("children") or []:
            walk(child, path + [child["name"]] if child.get("type") != "url" else path)

    for top in root.get("children") or []:
        walk(top, [top["name"]])
    return tools


def from_osint_directory(client: httpx.Client) -> list[dict]:
    html = client.get(OSINTDIR_URL, headers={"User-Agent": UA}).raise_for_status().text
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    payload = "".join(json.loads(f'"{c}"') for c in chunks)
    start = payload.find('{"categories":[')
    if start < 0:
        raise RuntimeError("osintdirectory payload format changed")
    categories, _ = json.JSONDecoder().raw_decode(payload[start:])
    tools = []
    for cat in categories["categories"]:
        for t in cat.get("tools") or []:
            tools.append(
                {
                    "name": t["name"],
                    "url": t["url"],
                    "category": cat["name"],
                    "path": [cat["name"]],
                    "description": t.get("description") or "",
                    "pricing": "unknown",
                    "sources": ["osintdirectory"],
                }
            )
    return tools


def merge(primary: list[dict], extra: list[dict]) -> list[dict]:
    by_url = {_norm_url(t["url"]): t for t in primary}
    for t in extra:
        key = _norm_url(t["url"])
        if key in by_url:
            existing = by_url[key]
            existing["sources"] = sorted(set(existing["sources"]) | set(t["sources"]))
            if t["category"] not in existing.setdefault("also_in", []) and t["category"] != existing["category"]:
                existing["also_in"].append(t["category"])
            if not existing.get("description"):
                existing["description"] = t["description"]
        else:
            by_url[key] = t
    return list(by_url.values())


def main() -> int:
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        ofw = from_osint_framework(client)
        print(f"osintframework: {len(ofw)} tools")
        try:
            odir = from_osint_directory(client)
            print(f"osintdirectory: {len(odir)} tools")
        except Exception as exc:  # keep going with what we have
            print(f"osintdirectory failed: {exc}", file=sys.stderr)
            odir = []
    tools = merge(ofw, odir)
    tools.sort(key=lambda t: (t["category"].lower(), t["name"].lower()))
    for i, t in enumerate(tools):
        t["id"] = i
    OUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sources": {
                    "osintframework": {"url": "https://osintframework.com/", "license": "MIT", "count": len(ofw)},
                    "osintdirectory": {"url": OSINTDIR_URL, "count": len(odir)},
                },
                "tools": tools,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(tools)} tools -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
