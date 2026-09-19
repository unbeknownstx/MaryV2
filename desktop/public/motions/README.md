# Mary Desktop Motion Assets

This folder is the local Desktop body-animation slot. Motion binaries are
replaceable presentation assets; they never define Mary's identity, memory,
relationship state, or reasoning.

Mary Desktop uses the official MIT-licensed `@pixiv/three-vrm-animation`
runtime. Add creator-owned/licensed `.vrma` files here and register them in
`manifest.json`.

Example:

```json
{
  "version": "1",
  "motions": [
    {
      "motion_id": "talk_neutral",
      "uri": "./motions/talk_neutral.vrma",
      "loop": true,
      "fade_in_ms": 180,
      "fade_out_ms": 240,
      "source": "creator_owned",
      "license": "creator_owned"
    }
  ]
}
```

The `motion_id` must match Mary's semantic MotionLibrary IDs. If a registered
VRMA cannot load, the renderer marks that asset unavailable for the session and
falls back to Mary's procedural semantic pose for that same motion ID.

Do not put Patreon-only Riko files or animation assets here unless their license
explicitly permits reuse. Riko is a design/reference source; Mary's renderer is
implemented independently.
