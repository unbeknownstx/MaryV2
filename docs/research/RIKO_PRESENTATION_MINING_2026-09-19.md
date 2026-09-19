# Riko Presentation Mining — 2026-09-19

## Scope and licensing boundary

This pass mines **official public evidence only** from RayenAI's MIT public repository and RayenAI's own public Patreon descriptions. It does not use redistributed Patreon/private source code.

The older public Riko repository is MIT licensed and shows the original small runtime: Faster-Whisper speech recognition, OpenAI-compatible dialogue/history, YAML character configuration and GPT-SoVITS speech. RayenAI's later public posts document the product's presentation evolution without exposing all private implementation details.

Official references:

- https://github.com/rayenfeng/riko_project
- https://www.patreon.com/RayenAI/posts/riko-project-v2-168551391
- https://www.patreon.com/RayenAI/posts/riko-project-app-169226252
- RayenAI Patreon development posts for animation, rooms/VR and MCP/tool calling

## What is worth taking

### 1. Model-directed acting, not model-owned rendering

Riko V2 publicly describes the model selecting expressions and animations during a reply. Mary already has a stronger owner for this idea: the canonical PerformancePacket.

Adoption rule:

    TurnMind / ExpressionDirector
              |
              v
       PerformancePacket
              |
              v
    surface capability projection
        /       |        \
   Desktop     PWA      iPhone
       |
   VRM renderer

The renderer never infers Mary's personality from raw text and never becomes an identity or emotion owner.

### 2. One character, many bodies

Riko demonstrates VRM desktop, transparent overlay and VR-style presentation. Mary keeps one canonical Core and treats bodies as replaceable surfaces.

mary.expression.surface_performance now makes this explicit. Each surface has truthful render affordances and an explicit degradation path. A surface may fail to render a gesture while still rendering the same canonical text and voice.

### 3. Layered motion

Riko's public development notes describe Mixamo/layered animation and improved animation state handling. Mary already has:

- PerformancePacket segments/beats;
- semantic MotionCue selection;
- deterministic micro-reactions;
- desktop head/gaze/chest/idle movement;
- lip-sync alignment;
- procedural semantic-pose fallback.

Next renderer milestone is real licensed/local VRMA/FBX playback behind the same semantic motion IDs. Binary motion assets stay outside Core authority.

### 4. Character Studio

Riko's photo/pose workflow and lighting sandbox are high-value presentation ideas. Desktop now has a first Character Studio pass inside Voice & Avatar:

- local expression preview;
- semantic pose/motion preview;
- full/portrait/close framing;
- key/fill/rim sliders;
- balanced/soft/neon/dramatic light presets;
- transparent WebGL PNG capture;
- copyable presentation-only stage setup JSON.

These controls operate only on the renderer. They cannot write memory, relationship, identity, emotion authority or cognition.

### 5. Surface parity

PWA already consumed Mary's canonical PerformancePacket. Native iPhone previously decoded display_hints but ignored the performance packet for normal turns.

Native iPhone now:

- retains the latest DeliveryPlan and PerformancePacket;
- passes the same DeliveryPlan into Core voice synthesis;
- derives expression/gaze/head/energy presentation cues;
- gives the Mary stage bounded breathing/gaze/head/energy motion;
- visibly indicates when canonical Presence/performance direction is linked.

This remains a 2D-art projection, not a fake claim of full VRM facial animation.

### 6. Lighting and scene state

Riko's rooms and lighting reinforce Mary's existing architecture:

- LiveScene = ephemeral current situational context;
- avatar/presentation state = body projection;
- future Mary World/Unity = replaceable world/body capability;
- canonical world model/memory = separate truth owners.

Do not create a second persistent scene-brain inside Unity, VRM or a desktop renderer.

### 7. Voice is a renderer

Riko's Fish Audio + GPT-SoVITS choice reinforces an existing Mary rule. DeliveryPlan owns performance direction; ElevenLabs, Fish Audio, GPT-SoVITS, Kokoro or a future local Mary voice are interchangeable renderers.

### 8. Diagnostics are product presentation

Riko's setup/check scripts solve a real companion-software problem: complex presentation stacks fail in partial ways.

scripts/doctor.py now reports:

- PerformancePacket contract;
- per-surface projection contract;
- semantic motion catalog/policy;
- Three-VRM renderer dependency;
- optional local Mary VRM body presence;
- PWA packet consumption;
- native iPhone presentation linkage.

Missing optional body assets remain warnings rather than Core startup failures.

## Deliberately deferred

These are worthwhile, but not ready to claim as implemented:

- real VRMA/FBX/Mixamo clip playback;
- drag-to-position 3D lights;
- arbitrary imported 3D rooms;
- locomotion/navigation through rooms;
- full transparent desktop companion overlay;
- native Quest/VR body;
- surface-negotiated capture/scene APIs;
- a complete animation asset browser/retargeter.

All should attach beneath the existing PerformancePacket / SurfacePerformance / LiveScene boundaries.

## Cohesion target

Mary's presentation loop is not a feature checklist. It is the visible end of the same system:

    Identity <-> Agency <-> Embodiment
         \        |        /
              Presence
                 |
       Desktop / iPhone / Stream / VR
                 |
             Experience
                 |
      perception / outcomes / context
                 |
          canonical owners

The presentation layer should make that flow observable. Structure can remain quiet; active conversion can be represented visually as the yellow current through the system without turning presentation telemetry into canonical truth.
