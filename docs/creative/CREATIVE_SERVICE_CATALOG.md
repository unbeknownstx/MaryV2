# MaryV2 Creative Service Catalog

Mary Studio can now plan book, manga, animation/video, audio-drama, and mixed-media productions.
`CreativeServiceRegistry` lets Mary know which external creative capabilities you have configured and
their price hints **without storing credentials or executing anything**.

## Example catalog

Create a private JSON file outside source control:

```json
{
  "capabilities": [
    {
      "provider": "my-video-provider",
      "capability": "video.render",
      "model": "anime-model",
      "available": true,
      "cost_per_unit_usd": 5.0,
      "unit": "job",
      "quality": "high"
    },
    {
      "provider": "my-image-provider",
      "capability": "image.generate",
      "cost_per_unit_usd": 0.10,
      "unit": "job"
    }
  ]
}
```

Then:

```powershell
$env:MARY_CREATIVE_SERVICE_CATALOG = "C:\MarySources\creative_services.json"
```

The registry stores no keys/tokens. Actual API adapters are separate integrations and remain subject
to MaryV2 permission and paid-action approval boundaries.

## Cross-media formats

- `book` → text development → edit → document assembly
- `manga` → image/reference jobs → lettering → document assembly
- `animation` → reference-frame jobs → motion render → voice/audio → edit assembly
- `short_video` → video render → optional voice/audio → edit assembly
- `audio_drama` → voice → sound → audio edit
- `mixed_media` → combined visual/video/audio pipeline

Creator drawings, manuscripts, storyboards, and voice takes can be attached as `CreativeReference`
objects and retain `creator_authored` provenance through the production plan.
