# Surface brief: Sounding app (frontend/src)

Scope: all app routes (Recon, World map, File metadata, Tool library, Settings). Mode: **Operate**.
Audience/task: analysts running infrastructure sweeps in a dim room over long sessions. The work: enter a target, read answers as they land, pivot on findings, export.
Constraints: keep every function, route and data contract; readability over atmosphere; dark scene.
Build path: code-led (no image generation in this harness; not stored as a preference).
Seed: the impeccable launcher is not installed, so there is no concept-seed key. The direction was ranked manually and chosen by the user from four cards (flight strips, transit map, bench instrument, SOC canon).

## Direction contract

THESIS: The sweep is air traffic. Each source is a flight progress strip printed for the target: it waits in the inbound bay, lands in the answered bay with a grease-pencil tick, or is struck through when it fails. This refuses the category default of a neon-on-black terminal with generic cards.

OWN-WORLD: A blue-grey console rack (#1C2227 ground, #262D33 bays, #333C44 rails) holding dimmed buff paper strips (#D8D2C0, ink #1F2429). Plastic strip holders are coloured by category (registration blue, DNS green, routing yellow, web orange, history violet, threat red) and carry the category code. Radar-scope cyan (#62C6D4) marks the action, focus and links. Grease-pencil blue ticks and red strikes are SVG strokes. B612 (Airbus cockpit face) is used for everything, and indicator values use tabular, slashed-zero figures. B612 Mono is reserved for raw JSON. (This is an adaptation made after the first captures: mono gave punctuation a full cell and spaced `1.1.1.1` apart. Principle 4, readability before atmosphere, wins.)

STORY: The analyst types a target onto the active strip, confirms authorization in the strip's own box and presses Sweep. Strips print into the inbound bay, and the radar scope plots each answer as a blip whose distance from centre is its latency. Strips land in arrival order. Discovered entities collect in the handoff tray, and one click sweeps any of them.

FIRST VIEWPORT: Across the top is a full-width active strip: holder tab, target field in large type, detected type, scope state, authorization box and a Sweep box at the right end. Below it on the left are the inbound bay (a row of printed stubs), the answered bay and the standby bay. On the right are the radar scope (square, about 300px) and the handoff tray beneath it.

FORM: Flight-strip board (ATC flight progress strips), first of seven in my ranked list; seed key n/a (launcher unavailable).

Signature interaction: a strip slides down into the answered bay while its grease tick draws (220ms / 320ms ease-out). The radar sweep rotates while a sweep runs, and each blip lights as its strip lands. Reduced motion shows the final states instantly.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
