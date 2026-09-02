"""Small public-feed helpers for ephemeral World Context.

This module intentionally parses headline metadata only. It does not scrape
article bodies, own current-world truth, or write memory. Network execution is
kept in explicit node-side scripts.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from typing import Iterable
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET


GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


@dataclass(frozen=True)
class FeedHeadline:
    title: str
    link: str
    source: str = "Google News RSS"
    published: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title[:300],
            "link": self.link[:800],
            "source": self.source[:180],
            "published": self.published[:120],
        }


def google_news_search_url(query: str, *, when: str = "1d") -> str:
    value = " ".join(str(query or "").split()).strip()
    if not value:
        raise ValueError("world feed query is required")
    if when:
        value = f"{value} when:{str(when).strip()[:8]}"
    return GOOGLE_NEWS_SEARCH.format(query=quote_plus(value))


def _text(node: ET.Element | None, name: str) -> str:
    if node is None:
        return ""
    child = node.find(name)
    return "" if child is None or child.text is None else " ".join(unescape(child.text).split())


def parse_rss_headlines(xml_text: str, *, limit: int = 6) -> list[FeedHeadline]:
    root = ET.fromstring(str(xml_text or ""))
    output: list[FeedHeadline] = []
    seen: set[tuple[str, str]] = set()
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        if not title or not link:
            continue
        key = (title.casefold(), link)
        if key in seen:
            continue
        seen.add(key)
        source_node = item.find("source")
        source = ""
        if source_node is not None and source_node.text:
            source = " ".join(unescape(source_node.text).split())
        output.append(FeedHeadline(
            title=title,
            link=link,
            source=source or "Google News RSS",
            published=_text(item, "pubDate"),
        ))
        if len(output) >= max(1, min(20, int(limit))):
            break
    return output
