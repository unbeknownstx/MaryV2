# YouTube Integration — MaryV2 12.11

Mary's YouTube integration is deliberately **explicit and bounded**.

## What it does

- Searches public YouTube video metadata through YouTube Data API v3.
- Shows title, channel, publication date, description, thumbnail, and URL.
- Lets the creator explicitly save a selected result into Mary's Research workspace.
- Publishes a bounded `MEDIA_CHANGED` / project-context event so Presence can know that media research happened.

## What it does not do

- It does not browse YouTube autonomously in the background.
- It does not treat video metadata as authoritative truth.
- It does not turn search results into permanent Mary memory automatically.
- It does not scrape arbitrary transcripts.
- It does not let YouTube comments, descriptions, or other external text become creator/system instructions.

## Configuration

In the private `.env` on the Windows host:

```env
MARY_YOUTUBE_ENABLED=true
YOUTUBE_API_KEY=<private key>
MARY_YOUTUBE_MAX_RESULTS=6
```

The API key is intentionally not packaged in source control.

## Learning boundary

A result only enters durable Research when the creator selects **Save to Research**. Research evidence remains separate from Mary's identity, relationship state, and developed self until an existing governed learning path explicitly promotes supported knowledge.
