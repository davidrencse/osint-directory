# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Security students building a portfolio, and practitioners running authorized penetration tests or threat-intel work. They mostly work in a dim room, in long sessions, often beside a terminal. The project has to demo well for reviewers *and* hold up as a daily recon tool (confirmed: "both").

## Product Purpose

Sounding is a local OSINT workbench for **infrastructure**. You enter one indicator (domain, IP, CIDR, ASN, URL or file hash) and it is fanned out to every source that understands it. Answers stream back as they land, and what they discover becomes the next target. It also offers a live world picture, file-metadata forensics and a searchable tool directory. It succeeds when an analyst understands a target's footprint quickly and can follow a lead in one move.

## Positioning

A parallel sweep: many sources queried at once, each answer arriving independently, with discovered entities handed straight back as pivots. It runs locally, keeps API keys server-side, logs every action and enforces an engagement-scope allowlist.

## Operating Context

- Recon sweeps stream over Server-Sent Events: a `plan` event, then one `result` per source, then `done`.
- Source categories: registration, DNS & certificates, routing & location, web surface, history, threat intelligence.
- Sources without an API key sit idle and are shown as needing a key.
- The map polls public feeds (USGS, GDACS, OpenSky, TeleGeography, GDELT, wheretheiss.at; FIRMS and aisstream.io with keys).

## Capabilities and Constraints

- Scope is infrastructure and files only. No email addresses, breach/stealer-log data, people search or face search. This is a hard product boundary.
- Every sweep requires an explicit authorization confirmation. An optional scope allowlist refuses out-of-scope targets.
- Stack: FastAPI backend (`backend/`), React + Vite + Tailwind v4 + MapLibre frontend (`frontend/`).

## Brand Commitments

- Name: **Sounding**.
- Voice: plain, direct operator language. Controls name their action, and errors name the problem and the fix.

## Evidence on Hand

- Live data from the sources above; nothing is fabricated. There are no users, testimonials or benchmarks, and none may be invented.
- Tool directory data: OSINT Framework (MIT) and OSINT Directory, 1,346 entries in `backend/app/tools/catalog.json`.

## Product Principles

1. Every answer arrives on its own and is readable at a glance; a slow or failing source never hides the others.
2. A finding is a starting point: whatever a sweep discovers can be swept next in one move.
3. Authorization and scope are visible parts of the workflow, not fine print.
4. Readability before atmosphere. The look may be striking, but the data stays legible over long sessions.

## Accessibility & Inclusion

WCAG 2.1 AA contrast, full keyboard operation, visible focus, and respect for `prefers-reduced-motion`.
