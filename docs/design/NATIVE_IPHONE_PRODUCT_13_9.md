# MaryV2 13.9 — Native iPhone Product

Status: active product design contract for the SwiftUI iPhone surface.

## Goal

The iPhone app should feel like a polished personal companion application first and a systems dashboard second. It remains a surface of the same canonical Mary Core; it never owns identity, relationship, memory, developed self, routing, or permissions.

## Research synthesis

The 13.9 pass reviewed current iPhone companion patterns across Nomi, Kindroid, Replika, Character.AI and other 2026 companion products, plus the open-source AIRI/Open-LLM-VTuber direction already studied for Mary.

Patterns worth adopting:

- conversation and voice are one tap away from the primary surface;
- the companion's visual presence is prominent without consuming the whole app;
- memory/relationship continuity is shown as understandable product context rather than backend counters;
- voice calls deserve a dedicated, calm, FaceTime-like presentation;
- shared activities should be obvious product affordances rather than hidden prompt engineering;
- native navigation, haptics, accessibility and safe-area behavior matter more on iPhone than transplanting a web dashboard;
- relationship context should be visible but should not use streaks, hearts-as-currency, urgency timers or manipulative retention loops.

Mary-specific differences:

- there is one authored/persistent Mary rather than a character marketplace;
- private/public performance context is a projection of the same Mary;
- relationship state comes from canonical Core history;
- nodes/providers are capabilities and stay out of normal companion UI unless the creator opens diagnostics;
- creator work and shared creative projects remain first-class because Mary is also a collaborator.

## Primary navigation

The five persistent bottom destinations are:

1. **Home** — Mary now, relationship context, continue-work, quick shared-life actions.
2. **Talk** — conversation-first chat, voice entry, conversation/performance controls.
3. **Together** — relationship context and shared-life activities.
4. **Work** — tasks/projects/study/creative collaboration.
5. **More** — memory, growth, focus, media, devices, integrations and settings.

Focus remains available from More, but does not consume one of the five primary product slots.

## Together

`TogetherView` is a native presentation over `performance_hardening.relational_presence` from the canonical dashboard projection.

It may display:

- friend / close / romantic / partner mode;
- active shared activity if Core has one;
- bounded proactive-presence proposal count;
- memory continuity count;
- private/public context.

It may not directly edit `relationship.json`, manufacture memories, or pretend an activity was canonically started when Core did not record it.

Until authenticated relational write actions are added to the Core single-writer dispatcher, tapping Watch/Play/Create/Study/Work/Music/Date/Unwind prepares a natural-language activity prompt and moves to Talk. This preserves user intent without bypassing Core authority.

## Assets

13.9 deliberately reuses approved bundled Mary artwork and Apple's system SF Symbols/materials. Public competitor screenshots were used only as visual research references and are **not** copied into the app. This avoids provenance/licensing ambiguity while keeping Mary visually canonical.

Bundled preferred art remains:

- `mary-reference.jpeg`
- `mary-stream-room-reference.png`
- `mary-neon-night-manga.png`
- `mary-neon-reference-sheet.png`

## Native experience rules

- minimum interactive target: 44 pt;
- preserve reduced-motion behavior;
- use haptics for selection/send/voice actions, not for engagement pressure;
- keep chat functional if TTS/avatar/relationship projection is unavailable;
- show Core connection failure honestly and keep local presentation stable;
- do not expose provider keys, backend internals, node permission machinery or diagnostic payloads on normal Home/Talk/Together screens;
- no relationship streaks, scarcity timers, jealousy mechanics or guilt prompts.

## 13.9 implementation

- rebuilt Home around Mary's presence and shared context;
- rebuilt Talk around conversation rather than avatar/dashboard chrome;
- added Together as a first-class destination;
- added eight shared-life starters;
- upgraded voice call presentation;
- preserved Work and Focus;
- added relational projection from the existing 13.8 Core dashboard;
- added native haptics and accessibility labels;
- advanced native app metadata to 0.5 (build 5).

## Deliberate follow-up

The next Core-side change should add authenticated, bounded relational runtime actions (`relationship.set_mode`, `shared_activity.start/note/complete/cancel`) through the existing single-writer Core action boundary. Once that exists, the native controls can mutate canonical relationship/shared-activity state without any direct file write or second authority path.
