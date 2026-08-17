from datetime import datetime, timezone

from mary.learning.grounding import ResearchGrounder
from mary.learning.researcher import ResearchSource
from mary.learning.source_resolver import SourceResolver


def test_source_resolver_canonicalizes_and_deduplicates_tracking_urls():
    resolver = SourceResolver()

    thin = ResearchSource(
        id="thin",
        title="Python release",
        url="https://python.org/downloads/release/python-3150rc1/?utm_source=x",
        content="Short snippet.",
        metadata={"score": 0.9, "content_source": "snippet"},
    )
    rich = ResearchSource(
        id="rich",
        title="Python 3.15.0rc1 release",
        url="https://python.org/downloads/release/python-3150rc1/#details",
        content="A" * 2500,
        metadata={"score": 0.8, "content_source": "raw_content"},
    )

    resolved = resolver.resolve(
        "latest Python release",
        [thin, rich],
    )

    assert len(resolved) == 1
    assert resolved[0].id == "rich"
    assert resolved[0].url == "https://python.org/downloads/release/python-3150rc1"
    assert resolved[0].metadata["source_resolution"]["entity_domain_match"] == 1.0


def test_resolved_direct_primary_page_outranks_generic_aggregator_hub():
    resolver = SourceResolver()
    grounder = ResearchGrounder()
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)

    aggregator = ResearchSource(
        id="hub",
        title="Python | InfoWorld",
        url="https://www.infoworld.com/python",
        content="Python news category page with several stories.",
        metadata={
            "score": 0.97,
            "published_date": "2026-08-10",
            "content_source": "snippet",
        },
    )
    official = ResearchSource(
        id="official",
        title="Python 3.15.0rc1",
        url="https://www.python.org/downloads/release/python-3150rc1/",
        content=(
            "Python 3.15.0rc1 is the first release candidate of Python 3.15. "
            "Released August 4, 2026. " + "Details " * 250
        ),
        metadata={
            "score": 0.78,
            "published_date": "2026-08-04",
            "content_source": "raw_content",
        },
    )

    resolved = resolver.resolve(
        "latest Python release news",
        [aggregator, official],
    )
    ranked = grounder.rank_sources(
        "latest Python release news",
        resolved,
        now=now,
    )

    assert ranked[0][0].id == "official"
    assert ranked[0][1].primary_source is True
    assert ranked[0][1].resolution_score > ranked[1][1].resolution_score
    assert ranked[1][0].metadata["source_resolution"]["generic_index"] is True
