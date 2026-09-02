"""Refresh stale Mary World Pulse lanes from a public headline feed.

This script is optional and node-side. It asks canonical Core which lanes need
refreshing, fetches bounded public RSS headline metadata, and returns each item
through the typed `world.ingest` action. Nothing here is Mary memory or canon.
"""
from __future__ import annotations

import argparse
import os
from time import sleep
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from mary.knowledge.public_feeds import google_news_search_url, parse_rss_headlines
from mary.protocol.client import MaryClient


def fetch_text(url: str, *, timeout: float = 15.0) -> str:
    request = Request(url, headers={"User-Agent": "MaryV2-WorldPulse/1", "Accept": "application/rss+xml, application/xml, text/xml"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - generated fixed-host Google News RSS URL
        return response.read(2_000_000).decode("utf-8", errors="replace")


def refresh_once(client: MaryClient, *, force: bool = False, lane_limit: int = 4, headlines_per_lane: int = 4) -> dict:
    plan = client.runtime_action("world.refresh_plan", {"force": force, "limit": lane_limit})
    due = list((plan or {}).get("due") or [])
    result = {"lanes": 0, "items": 0, "errors": []}
    for lane in due:
        name = str(lane.get("lane") or "general")[:60]
        query = str(lane.get("query") or "").strip()
        if not query:
            continue
        try:
            feed_url = google_news_search_url(query)
            headlines = parse_rss_headlines(fetch_text(feed_url), limit=headlines_per_lane)
            if not headlines:
                result["errors"].append(f"{name}: no headlines")
                continue
            for headline in headlines:
                client.runtime_action("world.ingest", {
                    "topic": headline.title,
                    "summary": headline.title,
                    "source": headline.source,
                    "lane": name,
                    "confidence": 0.62,
                    "ttl_hours": float(lane.get("ttl_hours", 24.0) or 24.0),
                    "url": headline.link,
                })
                result["items"] += 1
            result["lanes"] += 1
        except Exception as exc:  # one external lane must not stop Mary or other lanes
            result["errors"].append(f"{name}: {type(exc).__name__}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--watch", action="store_true", help="repeat refresh checks; explicit foreground process only")
    parser.add_argument("--interval-minutes", type=float, default=30.0)
    parser.add_argument("--lane-limit", type=int, default=4)
    parser.add_argument("--headlines-per-lane", type=int, default=4)
    args = parser.parse_args(argv)
    load_dotenv()
    core_url = os.getenv("MARY_CORE_URL", "").strip()
    core_token = os.getenv("MARY_CORE_TOKEN", "").strip()
    if not core_url or not core_token:
        print("MARY_CORE_URL and MARY_CORE_TOKEN are required")
        return 2
    client = MaryClient(core_url, token=core_token, device_id="world-pulse-node", surface="world_context", timeout=20)
    while True:
        result = refresh_once(client, force=args.force, lane_limit=max(1, min(8, args.lane_limit)), headlines_per_lane=max(1, min(8, args.headlines_per_lane)))
        print(f"World Pulse: {result['lanes']} lanes · {result['items']} items · {len(result['errors'])} errors", flush=True)
        for error in result["errors"]:
            print(f"  {error}", flush=True)
        if not args.watch:
            return 0
        args.force = False
        sleep(max(300.0, float(args.interval_minutes) * 60.0))


if __name__ == "__main__":
    raise SystemExit(main())
