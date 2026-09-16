# MaryV2 Creator Lab

Creator Lab is the Mary-centered path from **something the creator has** to **something Mary helps make**.

Examples:

- Drop in a generated Mary image -> ground the image -> Mary writes a caption in her own public voice -> Mary performs it through canonical voice -> optionally plan a Reel/video around the same asset.
- Drop in a storyboard/reference -> preserve it as creative authority -> derive shot/image/video jobs without silently reinterpreting canon.
- Start with only an idea -> Mary authors a script/caption -> voice synthesis uses her delivery plan -> approved image/video workers can render derivatives.

## Core rule

Creator Lab is coordination, not another identity. Mary Core remains the sole owner of identity, relationship, character, memory, growth, agency, emotion and provider policy. Creative assets and generated derivatives are workspace artifacts.

## Multimodal grounding

A URI or file reference alone does **not** mean Mary saw an image. `mary.creative.creator_lab` therefore distinguishes:

- `perception_description`: output from an explicitly available vision/perception capability;
- `creator_description`: trusted task context supplied by the creator;
- `unseen_asset`: no visual description is available yet.

For an unseen image, the first planned job is `vision.describe`. Mary authors a reaction/caption only after grounded visual context exists. Perception output is context-only: it does not become lived memory or creator biography.

## Reusable creative packet

`build_creator_packet()` compiles one asset + intent into provider-neutral jobs. Current job vocabulary includes:

- `vision.describe`
- `mary.author`
- `voice.synthesize`
- `image.generate`
- `video.render`

The packet can request a Mary caption/script, Mary voice, an image variant, and/or a video brief. It deliberately does not execute providers, spend money, write files, or publish.

## Voice

Mary-authored text should reuse the existing canonical `delivery_plan` / `performance_packet` bridge rather than sending flat text to TTS. That lets the same line carry Mary-specific pacing, emphasis and expression into voice and later animation/VTuber surfaces.

## Cohesive product flow

1. Creator chooses or creates an asset.
2. The asset is grounded by creator description or a bounded perception capability.
3. Canonical Mary authors the reaction, caption, narration or script.
4. The creator can edit/approve/reject public-facing text.
5. Mary's voice is synthesized from the canonical delivery plan.
6. Optional image/video workers receive the same grounded asset context, Mary-authored text, voice and continuity constraints.
7. Rendered results return to the production workspace as candidate assets.
8. Publishing remains a separate explicit approval/permission boundary.

This connects Social Presence and Production Studio rather than creating parallel silos: Social Presence owns public proposal/review continuity; Production Studio owns production artifacts; Creator Lab compiles the cross-media workflow between them.
