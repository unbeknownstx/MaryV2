# MaryV2 13.67 — Desktop Product Polish

13.67 is the presentation-hardening pass on top of the 13.66 Desktop product
shell. It does not introduce a second Mary, a new state owner, or a new routing
authority.

## Goal

Make Mary Desktop feel like one finished companion product instead of several
historical UI generations rendered at the same time.

The pass keeps every existing workspace and runtime surface, but gives them one
visual hierarchy:

1. Mary and the current conversation;
2. human-readable Core / Compute / Voice / Presence state;
3. contextual companion information;
4. work/creative/study/presence workspaces;
5. deep runtime diagnostics only when explicitly opened.

## Final-cascade contract

The Desktop has several intentionally retained historical style layers because
older functional surfaces still depend on their selectors. 13.67 therefore
adds a final presentation layer at:

`desktop/public/product-shell-13-67.css`

Vite injects it after `polish-13-7.css` and
`relational-13-8.css`.

The final layer explicitly clears inherited decorative properties instead of
assuming newer geometry rules overwrite them. This matters for old
pseudo-elements and hover effects whose backgrounds, animations or cursors
would otherwise survive into the current product.

Cleared/reduced legacy effects include:

- full-window scanline overlay;
- old HUD-corner background on the main stage;
- rotating presence-orb animation;
- custom game cursors;
- avatar debug HUD chips;
- generic hover lifts/glows on primary product cards.

No functional DOM nodes are removed by this presentation pass.

## Talk stage

Talk remains the product center.

- conversation occupies the left reading surface;
- Mary occupies the larger right presence surface;
- Core / Compute / Voice / Presence remains a compact human-readable status
  projection;
- chat bubbles use filled, opaque surfaces;
- state changes use restrained edge emphasis rather than whole-window glow;
- the composer is visually attached to the conversation instead of reading as
  a separate HUD.

The live `MaryCosma.vrm` path remains unchanged. If WebGL/VRM presentation is
unavailable, the fallback presentation deterministically uses the canonical
Mary reference art rather than cycling through several images like a
slideshow.

## Workspaces

Home, Memories, Personality, Growth, Studio, Study, Command, Focus, Stream,
Gallery, Media, Voice & Avatar, Mind, Runtime and Settings share one workspace
grammar:

- solid workspace frame;
- consistent header and scrolling body;
- common panel radius/border/background;
- common section titles and data rows;
- common button treatment;
- responsive three/two/one-column grids.

Presentation does not change any workspace authority or backend API.

## Inspector

The inspector remains contextual and secondary. It is intentionally sacrificed
before Talk/Mary when width is constrained.

The inspector can summarize current Mary state, continuity, activity and
runtime evidence, but normal conversation never becomes dependent on it.

## Responsive order

The compression policy is:

1. reduce rail widths;
2. collapse three-column workspace grids to two;
3. hide the inspector;
4. collapse navigation labels to icons;
5. preserve both conversation and Mary presence for as long as the Desktop
   host remains within the supported minimum width.

Short displays hide secondary sidebar utility cards before shrinking the
conversation into an unusable region.

## Accessibility

13.67 preserves:

- visible keyboard focus;
- reduced-motion behavior;
- high-contrast overrides;
- readable opaque surfaces;
- scrolling workspace bodies;
- no information that exists only as glow/animation.

## Launcher

The launcher now uses the same opaque navy/pink/violet language as Desktop and
clears its older cyber-grid/HUD decoration.

Its normal product contract remains:

- PLAY MARY;
- persistent Core;
- local + cloud compute;
- voice + avatar presence;
- optional staged updates;
- identity/memory remain with Mary Core.

The static installed-version fallback is updated to 13.67; runtime update
authority may still replace that display with authoritative installed/update
state.

## Version display

The Vite compatibility transform now rewrites historical 12.12 / 13.7 / 13.8
presentation labels to 13.67. This is a display compatibility rule only. It does
not rewrite Core protocol, subsystem versioning, persisted data, provider
metadata or runtime authority.

## Regression protection

`tests/desktop/test_desktop_product_shell_13_67.py` protects:

- final stylesheet injection order;
- removal of legacy HUD residue;
- deterministic avatar fallback while preserving VRM;
- Talk/Mary stage priority;
- unified workspace grammar;
- accessibility rules;
- responsive priority;
- launcher consistency.

The older 13.66 tests remain in place to protect the architectural shell that
13.67 polishes.
