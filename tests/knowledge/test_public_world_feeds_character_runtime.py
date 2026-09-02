from mary.knowledge.public_feeds import google_news_search_url, parse_rss_headlines


def test_google_news_url_is_bounded_search_feed():
    url = google_news_search_url("current games and anime")
    assert url.startswith("https://news.google.com/rss/search?")
    assert "when%3A1d" in url
    assert "current+games+and+anime" in url


def test_rss_parser_extracts_headline_metadata_only_and_dedupes():
    xml = """<?xml version='1.0'?><rss><channel>
      <item><title>Mary-worthy game news</title><link>https://example.test/a</link><pubDate>Now</pubDate><source>Example</source><description>body should not be retained</description></item>
      <item><title>Mary-worthy game news</title><link>https://example.test/a</link><source>Example</source></item>
      <item><title>Anime release</title><link>https://example.test/b</link><source>Another</source></item>
    </channel></rss>"""
    rows = parse_rss_headlines(xml, limit=8)
    assert [x.title for x in rows] == ["Mary-worthy game news", "Anime release"]
    assert rows[0].source == "Example"
    assert "body should not" not in repr([x.to_dict() for x in rows])
