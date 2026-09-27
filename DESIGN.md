---
name: Sounding
description: Infrastructure OSINT workbench built as an air-traffic flight-strip board
colors:
  console-ground: "#000000"
  console-bay: "#0a0a0a"
  console-bay-raised: "#161616"
  console-rail: "#262626"
  console-text: "#ededed"
  console-text-2: "#a3a3a3"
  console-text-3: "#8a8a8a"
  strip-paper: "#0a0a0a"
  strip-paper-shade: "#1a1a1a"
  strip-paper-rule: "#1f1f1f"
  strip-ink: "#ededed"
  strip-ink-2: "#9e9e9e"
  radar-cyan: "#fafafa"
  radar-cyan-deep: "#525252"
  grease-blue: "#4ade80"
  grease-red: "#f87171"
  alert: "#f87171"
  ok: "#4ade80"
  holder-registration: "#60a5fa"
  holder-dns: "#34d399"
  holder-routing: "#facc15"
  holder-web: "#fb923c"
  holder-history: "#a78bfa"
  holder-threat: "#f87171"
  holder-target: "#fafafa"
  holder-empty: "#525252"
  holder-ink: "#000000"
typography:
  headline:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 400
    lineHeight: 1.3
    fontFeature: "\"tnum\", \"zero\""
  body:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "\"tnum\""
  label:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.3
  caption:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.2
  code:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  paper: "2px"
  control: "3px"
  holder: "4px"
spacing:
  cell-y: "7px"
  cell-x: "12px"
  strip-gap: "8px"
  section: "40px"
components:
  button-primary:
    backgroundColor: "{colors.radar-cyan}"
    textColor: "{colors.holder-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-primary-disabled:
    backgroundColor: "{colors.console-bay-raised}"
    textColor: "{colors.console-text-3}"
  button-primary-on-paper-disabled:
    backgroundColor: "{colors.strip-paper-shade}"
    textColor: "{colors.strip-ink-2}"
  button-quiet:
    textColor: "{colors.console-text-2}"
    rounded: "{rounded.control}"
    padding: "4px 10px"
  button-quiet-hover:
    backgroundColor: "{colors.console-bay-raised}"
    textColor: "{colors.console-text}"
  strip-holder:
    backgroundColor: "{colors.holder-empty}"
    textColor: "{colors.holder-ink}"
    rounded: "{rounded.holder}"
    padding: "2px 2px 2px 0"
  strip-body:
    backgroundColor: "{colors.strip-paper}"
    textColor: "{colors.strip-ink}"
    rounded: "{rounded.paper}"
  strip-cell:
    padding: "7px 12px"
    typography: "{typography.body}"
  field:
    backgroundColor: "{colors.console-bay}"
    textColor: "{colors.console-text}"
    rounded: "{rounded.control}"
    padding: "12px"
  nav-item:
    textColor: "{colors.console-text-2}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  nav-item-active:
    backgroundColor: "{colors.console-bay-raised}"
    textColor: "{colors.console-text}"
---

# Design System: Sounding

> **Revision (2026-09-27): black and sleek.** At the user's request the console is now true black with hairline (#262626) borders. "Paper" strips are near-black rows (#0a0a0a) with light text. A category's holder colour survives only as a small coded tag with a glowing dot on the strip's left cell, not a filled frame. White (#fafafa) replaces cyan as the single action and focus colour. The face is Geist (sans and mono). Corners are 8px for strips and 6px for controls. Where the prose below says paper, holder frame or Radar Cyan, read near-black row, coded tag and white. The token values in the frontmatter are current.

## Overview

**Creative North Star: "The Strip Board"**

Sounding is laid out like an air-traffic control position. The page is a blue-grey console rack. Every piece of work is a paper flight progress strip sitting in a plastic holder whose colour says which category it belongs to. A recon source, a map layer, a revealing metadata field and an API key are all strips. A strip that is printed on paper is live: it answered, it is showing, or it is set. An empty dashed holder is the absence: not run, hidden, or missing a key. That one state vocabulary carries every screen.

Density is operational, not decorative. Strips are narrow and packed in bays with a rail above each bay. Fields sit in ruled cells with small captions. The strip is the only container; there are no cards. The single piece of atmosphere is the radar scope. Its sectors are categories, its log-scale rings are response time, and its blips light as answers land. It is a real data graphic, not ornament.

The system is built for a dim room and long sessions. The ground is a mid-dark blue-grey, not black. The paper is a dimmed buff, not white. Radar cyan is the only accent that means "you can act here".

**Key Characteristics:**
- Paper strips in category-coloured holders, each with a three-letter code on its tab.
- Printed strip means active; empty dashed holder means inactive, missing or not applicable.
- Grease-pencil marks: a blue tick for an answer, a red cross and strikethrough for a failure.
- A radar scope plots latency by category; distance from the centre is response time.
- One typeface family (Geist, the Airbus cockpit face) at every size.

## Colors

A cool console and warm paper, with six holder colours doing the categorising and one cyan doing the acting.

### Primary
- **Radar Cyan** (#fafafa): the only action colour. It fills the primary button (Sweep, Download a clean copy, Save scope), the selected category in lists, the Globe/Flat toggle, focus rings on the console, links on the console, and the radar sweep. It also colours the holder of the active strip (TGT, FND, FIL), because that strip is where the user acts.

### Secondary
- **Holder colours**, one per source category, used only on strip holders, radar sectors and matching blips:
  - Registration blue (#60a5fa)
  - DNS green (#34d399)
  - Routing yellow (#facc15)
  - Web orange (#fb923c)
  - History violet (#a78bfa)
  - Threat red (#f87171)
  - Tab codes are always set in Holder Ink (#000000) for contrast.

### Tertiary
- **Grease Blue** (#4ade80) and **Grease Red** (#f87171): the controller's pencil. They appear only on paper: the tick, the cross, strikethroughs, and error text inside a strip.

### Neutral
- **Console Ground** (#000000): the page field.
- **Console Bay** (#0a0a0a): the nav rail, input fields, pivot rows, tool rows and field-group bars.
- **Raised Bay** (#161616): hover and the active nav item.
- **Rail** (#262626): bay rules, borders and dashed empty holders.
- **Console Text** (#ededed), **Text 2** (#a3a3a3) and **Text 3** (#8a8a8a): primary, secondary and faint text on the console. All three pass 4.5:1 on the ground.
- **Strip Paper** (#0a0a0a), **Paper Shade** (#1a1a1a) and **Paper Rule** (#1f1f1f): the strip surface, disabled paper controls, and the cell dividers.
- **Strip Ink** (#ededed) and **Ink 2** (#9e9e9e): text on paper.

### Named Rules
**The Holder Rule.** Holder colours classify; they never decorate. A colour appears on a holder, a radar sector or a blip for the category it names, and nowhere else.

**The One Action Rule.** Radar Cyan marks what can be acted on or where focus is. Nothing inactive is ever cyan.

**The Paper Is Live Rule.** Paper (#0a0a0a) is reserved for things that are live: answered sources, visible layers, set keys, the active target. Inactive items are drawn as empty dashed holders on the console, never as greyed-out paper.

## Typography

**Body Font:** Geist (with system-ui)
**Code Font:** Geist Mono (raw JSON responses only)

**Character:** A face designed for aircraft cockpit displays. Its letterforms are built to be told apart under stress (I/l/1, 0/O). Its parentheses are deliberately square. One family carries headings, labels, data and body.

### Hierarchy
- **Headline** (700, 1.75rem, 1.2): page titles such as "File metadata" and "Tool library".
- **Title** (400, 1.375–1.75rem, tabular slashed-zero figures): the target on the active strip and the swept indicator.
- **Body** (400, 0.9375rem, 1.45): prose, strip values and list items. Prose stays under 70ch.
- **Label** (700, 0.8125rem): bay headings, strip callsigns and holder codes, the codes spaced 0.04em.
- **Caption** (400, 0.6875rem): the field caption above a value inside a strip cell.

### Named Rules
**The Readable Indicator Rule.** IPs, hashes, domains and timings use Geist with tabular, slashed-zero figures, never a monospace. A monospace gives `.` a full cell and turns `1.1.1.1` into `1. 1. 1. 1`.

**The Sentence Case Rule.** Headings, captions and buttons use sentence case. Upper case is reserved for the three-letter holder codes and environment variable names.

## Layout

A left rail (14rem) holds the brand, the navigation and a short trust note. Below 768px it becomes a bottom tab bar. Content sits in a centred column capped at 1440px, with 28px gutters on desktop and 16px on phones. The recon board is a two-column grid: strip bays in a flexible column, and a 320px aside holding the radar, pivots and outside-tool links, which sticks on scroll above 1024px. Below 1024px the aside follows the bays.

Strips stack with an 8px gap. Bays are separated by 32–40px, and each bay opens with a heading, a count and a rail. Strip cells use 7px × 12px padding. On narrow screens strip grids wrap: the callsign and timing share row one, and the fields move to row two.

## Elevation & Depth

Depth comes from the physical strip, not from floating panels. A strip in its holder casts a short, soft offset shadow (`0 1px 0 rgb(0 0 0 / .35), 0 3px 8px -2px rgb(0 0 0 / .35)`), as if it sits proud of the rack. Everything else on the console is flat, separated by tone (ground, bay, raised bay) and hairline rails. Floating map panels carry one deeper ambient shadow (`0 10px 30px -6px rgb(0 0 0 / .65)`).

### Named Rules
**The Flat Rack Rule.** Only strips and floating map overlays cast shadows. Bays, rows and fields are flat and separated by tone.

## Shapes

The shapes are near-square, like cut paper and moulded plastic. Holders have 4px corners, the paper inside 2px, and controls 3px. Holders show 2px of colour around the paper, with a 3.25rem coded tab on the left. Empty holders are 1px dashed Rail outlines with the same tab geometry. The only circles are the radar scope and its rings; blips are squares, like radar returns.

## Components

### Buttons
- **Shape:** gently squared (3px).
- **Primary:** Radar Cyan fill, Holder Ink text, bold. On a strip it fills the strip's last cell. Hover brightens it by 10%.
- **Disabled:** Raised Bay with Text 3 on the console; Paper Shade with Ink 2 on paper.
- **Quiet:** text-only in Text 2, with a Raised Bay fill on hover (export actions, closing panels).
- **Destructive:** Rail outline that turns Alert (#f87171) on hover (Clear the cache). Stop sweep turns Grease Red.

### Strips (signature component)
- **Anatomy:** a holder of the category colour, a coded tab (REG, DNS, NET, WEB, HIS, INT, TGT, FIL, KEY and so on), and a paper body split into ruled cells. The callsign cell is the source or item name in bold with its origin host beneath. Field cells hold a caption over a value, up to three on desktop. The timing cell holds the latency or "cached", a grease mark and an expand chevron.
- **States:** landed (answered, blue tick); unable (callsign struck through in Grease Red, reason in a single field cell, red cross); waiting (a short stub strip at 80% opacity with a printing line along the bottom edge); not run or off (an empty dashed holder); highlighted (a 2px cyan outline, linked to the radar blip on hover).
- **Expanded:** the "back of the strip", a paper sheet under the strip indented past the tab, opened below a dashed fold. It holds every field, the source link and the raw-response toggle.
- **Motion:** a landing strip slides 14px down with a clip reveal (240ms, expo ease-out), then its grease tick is drawn (320ms, 140ms delay). Reduced motion shows the final state immediately.

### Radar Scope (signature component)
Sectors for the six categories, with codes in their holder colours. Log rings at 0.1 s, 1 s, 10 s and 60 s. Square blips in the category colour; a hollow square is a cached answer and a red × is a failure. Before and during a sweep, ghost dots on the rim show which sectors will report. While a sweep runs, a cyan wedge rotates (2.6s per turn). Hovering a blip shows a data block with the source name and timing on a leader line.

### Inputs / Fields
- **On a strip:** transparent over paper in Strip Ink, placeholder in Ink 2, focus drawn by the paper focus ring (Grease Blue).
- **On the console:** Console Bay fill, 1px Rail border, 3px corners; focus turns the border Radar Cyan.
- **Checkboxes:** a square outline in the current text colour, with a drawn tick that scales in (140ms).

### Navigation
The rail lists icon plus label in Text 2. Hover lifts to a Raised Bay fill. The active item has a Raised Bay fill, Console Text label and a Radar Cyan icon. On phones it is a bottom bar with short labels (Recon, Map, Files, Tools, Settings).

### Map overlays
The layer panel is a bay of layer strips grouped by kind; a printed strip is on the map and an empty holder is hidden. Feature popups are data blocks: a coded holder chip, the layer name, then field and value rows on Console Bay.

## Do's and Don'ts

### Do:
- **Do** express every on/off, set/missing or answered/not-run state as a printed strip versus an empty dashed holder.
- **Do** give every new category of thing a three-letter holder code and one holder colour, and use that colour everywhere the category appears.
- **Do** keep indicator values in Geist with tabular, slashed-zero figures.
- **Do** keep Radar Cyan for actions, selection and focus only.
- **Do** write bay headings in sentence case with a count, such as "Results 9 of 9".

### Don't:
- **Don't** set indicators or UI text in Geist Mono; it spaces punctuation apart. It is for raw JSON only.
- **Don't** wrap content in generic rounded cards; the strip is the container.
- **Don't** use a holder colour to decorate something outside its category.
- **Don't** grey out paper to show inactivity; use an empty holder.
- **Don't** add texture, bevels or faux-paper effects; the paper and plastic are flat colour.
