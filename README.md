# Sounding: OSINT workbench

A local dashboard for **infrastructure** reconnaissance and open-source situational awareness. You enter a domain, IP, network, ASN, URL or file hash, and every applicable source is queried in parallel. Results stream back as they arrive.

| Module | What it does |
| --- | --- |
| **Recon** | Sends one indicator to 20 sources (RDAP/WHOIS, DNS, zone-transfer check, certificate transparency, TLS, HTTP fingerprint and security headers, robots/security.txt, Wayback, RIPEstat BGP, ipinfo, Shodan, Censys, VirusTotal, AbuseIPDB, GreyNoise, OTX, urlscan, SecurityTrails, CIRCL hashlookup). Shows each as a waterfall row. Discovered hosts, IPs, prefixes and ASNs become one-click pivots. Exports to Markdown or JSON. |
| **World map** | A globe or flat map with live layers: USGS earthquakes, GDACS disaster alerts, NASA FIRMS fires, OpenSky aircraft, aisstream.io vessels, the ISS, submarine cables and landing points (TeleGeography), GDELT news and conflict/unrest events, and a day/night terminator. The layer set is kept in `?layers=`, so views can be shared. |
| **File metadata** | Upload a photo, PDF, Office document or media file. You get every embedded field, a "what this file reveals" summary (location, identity, device, timestamps, local paths), a GPS pin, hashes, and a one-click clean copy. JPEG and PNG are stripped losslessly. |
| **Tool library** | A searchable catalog of 1,346 tools merged from [OSINT Framework](https://osintframework.com/) (MIT) and [OSINT Directory](https://www.osintdirectory.com/tools). You can filter by pricing, sign-up, passive vs. active, and local install. Every entry is a plain link out. |
| **Settings** | Which API keys are set, an engagement-scope allowlist, cache control, and an activity log of every sweep and upload. |

## Scope

This tool covers infrastructure and file analysis, not people. It won't take email addresses, and it doesn't query breach dumps, stealer logs, people-search engines or face-search services. Every sweep requires an "I'm authorized" confirmation and is written to the activity log. If you set a scope allowlist, targets outside it are refused. Only sweep assets you own or have written permission to test.

## Running it

Requirements: Python 3.12+ with [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
# backend (http://127.0.0.1:8000)
cd backend
cp .env.example .env        # optional: add API keys
uv sync
uv run uvicorn app.main:app --reload --reload-dir app

# frontend (http://localhost:5173, proxies /api to the backend)
cd frontend
npm install
npm run dev
```

For a single-process setup, run `npm run build` in `frontend/`. The backend then serves the built app at http://127.0.0.1:8000.

Installing [ExifTool](https://exiftool.org/) on the backend machine widens the metadata module to every format ExifTool knows, and lets it strip any of them. Without it, the built-in parsers cover JPEG, PNG, TIFF, WebP, PDF, DOCX, XLSX, PPTX and common audio and video.

### Refreshing the tool catalog

```bash
cd backend
uv run python scripts/build_catalog.py
```

## Adding a recon source

1. Subclass `Pipeline` in `backend/app/recon/pipelines/` (see `network.py` for a small example). Set `name`, `label`, `category`, `accepts` and any `key_fields`, then return an `Output(summary, data, source_url, pivots)`.
2. Register it in `ALL` in `backend/app/recon/pipelines/__init__.py`.
3. If it needs a key, add the field to `Settings` in `app/config.py` and a signup link in `app/settings_router.py`.

The orchestrator handles concurrency, per-source timeouts, caching and error isolation. A failing source never stops a sweep.

## Tests

```bash
cd backend && uv run pytest
```

## API

The backend is a plain JSON API; interactive docs are at http://127.0.0.1:8000/docs.

- `GET /api/recon/stream?target=…&authorized=true` streams Server-Sent Events: `plan`, then one `result` per source, then `done`.
- `GET /api/recon/run?target=…&authorized=true` returns the same report as one JSON document.
- `GET /api/geo/{layer}?bbox=w,s,e,n` returns a GeoJSON FeatureCollection.
- `POST /api/metadata` (multipart `file`) analyses a file; `POST /api/metadata/strip` returns a cleaned copy.
- `GET /api/tools/catalog` returns the tool catalog.
"# osint-directory" 
