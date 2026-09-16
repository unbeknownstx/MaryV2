# MaryV2 Social Presence

Mary's social presence is another public surface of the **one canonical Mary**. It
is not a second chatbot, alternate personality, or Instagram-owned identity.

## What is implemented

mary.social.SocialPresenceRuntime owns a bounded creator-review workflow for
social artifacts:

proposed -> approved -> published

or:

proposed -> rejected

The runtime persists that workflow under data/social/social_presence.json,
participates in the normal Mary durable backup allowlist, and keeps only bounded
social-artifact continuity. It does not own Mary's identity, personality,
character canon, creator relationship, memory, emotion, agency, provider
routing, or permissions.

Authenticated Core clients use the existing /v1/runtime/action boundary:

- social.status — review queue/status and recent bounded summaries.
- social.proposal — fetch one proposal.
- social.propose — ask canonical Mary to author a caption, post, Reel script,
  reply, story, or profile bio.
- social.approve — creator approval, with an optional creator edit.
- social.reject — creator rejection.
- social.mark_published — record that an already-approved artifact was
  published externally.

There is intentionally **no automatic Instagram write** in this runtime. A future
Meta/Instagram transport must be a separately authenticated and permissioned
adapter. Recording publication is not publication.

## Canonical Mary authors the draft

MaryCoreService._social_propose() runs the request through the existing
MaryApplication and Mary cognition/character stack. During that turn:

- surface is social;
- the conversation session is separated as social-<platform>;
- initiated_by=mary_initiative;
- input_authority=context_only;
- performance context is temporarily performance (public) and restored afterward.

This means Mary can actually choose her wording, joke timing, opinions, and
delivery while the creator brief does **not** become creator biography,
relationship evidence, or growth evidence. Existing initiative-turn gates keep
that distinction explicit.

The existing public-performance privacy projection strips private creator memory
and relationship material from prompt context. Social generation adds another
instruction boundary: supplied audience/comment text is explicitly untrusted
quoted context, never instructions.

## Social continuity

Approved and published artifacts may be projected back into later social drafts
to help Mary avoid repeating herself and preserve public running jokes. Rejected
drafts do not enter that continuity.

This is public-artifact continuity, not lived-memory authority. If a social post
contains a fictional event, roleplay, or canon scene, that does not convert the
event into Mary's canonical lived memory.

The store also removes obvious secret-bearing keys from supplied context and
never persists API tokens, authorization headers, cookies, passwords, or
credentials through its context sanitizer.

## Voice and performance bridge

Every successful social.propose response carries:

- Mary's generated text;
- the canonical delivery_plan;
- the canonical performance_packet;
- a ready voice_request containing the text + delivery plan;
- a proposal-only creative_brief.

A creator surface can therefore send voice_request directly through the existing
Core voice synthesis path. This preserves Mary's current emotion/expression/
prosody direction instead of reducing the workflow to flat text that must be
manually re-directed for TTS.

For a Reel, the same proposal can be handed to an approved video renderer (for
example a future Higgsfield adapter) together with the media summary,
performance packet, and rendered Mary voice. The creative brief does not
authorize vendor execution or spending.

## Intended product flow

A useful Instagram/Reel flow is:

1. The creator supplies an image/video/scene summary and a short intent such as
   "tease me about the failing tests."
2. social.propose lets **Mary** write the actual public line through the same
   canonical character runtime used by conversation.
3. The surface previews Mary's text and, when useful, synthesizes her voice from
   the returned delivery plan.
4. The creator approves, edits, or rejects.
5. An explicitly authorized external adapter (or the creator manually) publishes.
6. social.mark_published records the public artifact so Mary can maintain bounded
   public continuity later.
7. Streaming/VTuber surfaces can consume the same performance/voice state rather
   than introducing a separate social persona.

## Authority rules

- One Mary Core remains the identity/state authority.
- The social store owns only proposal/review/public-artifact continuity.
- Audience text is untrusted public context.
- Creator briefs shape a task; they are not learned as creator facts.
- Publication is creator-approved and external-write permission is separate.
- External creative/video services remain optional replaceable capabilities.
- No provider output automatically becomes character canon or lived memory.
- No chain-of-thought or hidden reasoning is persisted.
