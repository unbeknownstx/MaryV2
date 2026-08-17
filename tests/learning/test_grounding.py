from datetime import datetime, timezone

from mary.learning.grounding import ResearchGrounder
from mary.learning.researcher import ResearchSource


def test_grounder_prefers_current_official_source_for_latest_query():
    grounder = ResearchGrounder()
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)

    official = ResearchSource(
        id="official",
        title="Python 3.15.0rc1 release",
        url="https://www.python.org/downloads/release/python-3150rc1/",
        content="Python 3.15.0rc1 was released August 4, 2026.",
        relevance=0.8,
        metadata={"score": 0.8, "published_date": "2026-08-04"},
    )
    stale_blog = ResearchSource(
        id="old",
        title="Python 3.14 release candidate",
        url="https://example.com/python-314-rc",
        content="December 9, 2025 release candidate coverage.",
        relevance=0.95,
        metadata={"score": 0.95, "published_date": "2025-12-09"},
    )

    ranked = grounder.rank_sources(
        "latest Python release news",
        [stale_blog, official],
        now=now,
    )

    assert ranked[0][0] is official
    assert ranked[0][1].primary_source is True
    assert ranked[0][1].observed_date == "2026-08-04"
    assert ranked[1][1].overall < ranked[0][1].overall


def test_grounder_marks_old_source_stale_for_dynamic_query():
    grounder = ResearchGrounder()
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    source = ResearchSource(
        id="old",
        title="Old release notes",
        url="https://example.com/releases/old",
        content="Published May 1, 2024.",
        metadata={"published_date": "2024-05-01"},
    )

    assessment = grounder.assess_source(
        "what is the latest release?",
        source,
        now=now,
    )

    assert assessment.stale_for_dynamic_query is True
    assert assessment.recency < 0.5


def test_grounder_metadata_is_attached_for_existing_evaluator():
    grounder = ResearchGrounder()
    source = ResearchSource(
        id="docs",
        title="Official documentation",
        url="https://docs.example.org/reference/",
        content="Reference documentation.",
        metadata={"score": 0.7},
    )

    assessment = grounder.assess_source(
        "documentation for example",
        source,
    )

    assert source.confidence == assessment.overall
    assert source.metadata["grounding"]["overall"] == assessment.overall
