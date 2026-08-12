"""
MaryV2 - Knowledge Sources

Defines the provenance system for Mary's knowledge.

A Source represents where information came from.

Examples:

    - web page
    - official documentation
    - academic paper
    - book
    - conversation
    - experiment
    - creator-provided information
    - internal observation

This module does NOT perform web searches or fetch URLs.

Web access belongs to:

    mary/tools/web.py

The source manager records and evaluates provenance after
information has been obtained.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# ================================================================
# SOURCE TYPES
# ================================================================


SOURCE_TYPES = {
    "web",
    "official",
    "documentation",
    "academic",
    "book",
    "conversation",
    "creator",
    "experiment",
    "observation",
    "system",
    "unknown",
}


SOURCE_STATUSES = {
    "active",
    "archived",
    "unverified",
    "invalid",
}


# ================================================================
# SOURCE
# ================================================================


@dataclass
class Source:
    """
    Represents a source of information.

    The source itself is not treated as truth.

    Instead, it provides provenance and metadata that can be used
    by the evaluator and knowledge manager.
    """

    id: str

    title: str

    source_type: str = "unknown"

    location: str = ""

    author: str = ""

    publisher: str = ""

    description: str = ""

    reliability: float = 0.5

    status: str = "unverified"

    accessed_at: str = ""

    published_at: str | None = None

    last_verified: str | None = None

    verification_count: int = 0

    contradiction_count: int = 0

    tags: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.reliability = _clamp(
            self.reliability
        )

        if self.source_type not in SOURCE_TYPES:
            self.source_type = "unknown"

        if self.status not in SOURCE_STATUSES:
            self.status = "unverified"

        if not self.accessed_at:
            self.accessed_at = _timestamp()

    # ============================================================
    # RELIABILITY
    # ============================================================

    def set_reliability(
        self,
        reliability: float,
    ) -> None:
        """
        Set source reliability.
        """

        self.reliability = _clamp(
            reliability
        )

    def increase_reliability(
        self,
        amount: float = 0.05,
    ) -> None:
        """
        Increase reliability.
        """

        self.set_reliability(
            self.reliability + amount
        )

    def decrease_reliability(
        self,
        amount: float = 0.05,
    ) -> None:
        """
        Decrease reliability.
        """

        self.set_reliability(
            self.reliability - amount
        )

    # ============================================================
    # VERIFICATION
    # ============================================================

    def verify(
        self,
        reliability: float | None = None,
    ) -> None:
        """
        Mark the source as verified.
        """

        self.status = "active"

        self.verification_count += 1

        self.last_verified = _timestamp()

        if reliability is not None:
            self.reliability = _clamp(
                reliability
            )

    def invalidate(
        self,
        reason: str = "",
    ) -> None:
        """
        Mark a source as invalid.
        """

        self.status = "invalid"

        if reason:
            self.metadata[
                "invalid_reason"
            ] = reason

    def archive(
        self,
    ) -> None:
        """
        Archive a source without treating it as invalid.
        """

        self.status = "archived"

    def mark_unverified(
        self,
    ) -> None:
        """
        Return a source to an unverified state.
        """

        self.status = "unverified"

    # ============================================================
    # CONTRADICTIONS
    # ============================================================

    def record_contradiction(
        self,
    ) -> None:
        """
        Record that information from this source contradicted
        another known claim.
        """

        self.contradiction_count += 1

        self._recalculate_reliability()

    # ============================================================
    # TAGS
    # ============================================================

    def add_tag(
        self,
        tag: str,
    ) -> None:
        """
        Add a normalized tag.
        """

        tag = str(
            tag
        ).strip().lower()

        if not tag:
            return

        if tag not in self.tags:
            self.tags.append(
                tag
            )

    def remove_tag(
        self,
        tag: str,
    ) -> None:
        """
        Remove a tag.
        """

        tag = str(
            tag
        ).strip().lower()

        if tag in self.tags:
            self.tags.remove(
                tag
            )

    # ============================================================
    # INTERNAL RELIABILITY
    # ============================================================

    def _recalculate_reliability(
        self,
    ) -> None:
        """
        Adjust reliability based on contradiction history.

        This is intentionally conservative.

        A single contradiction should not destroy trust in a
        source.
        """

        if self.contradiction_count <= 0:
            return

        penalty = min(
            0.25,
            self.contradiction_count * 0.03,
        )

        self.reliability = _clamp(
            self.reliability - penalty
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(
        self,
    ) -> dict[str, Any]:
        """
        Return a compact source representation.
        """

        return {
            "id": self.id,
            "title": self.title,
            "type": self.source_type,
            "location": self.location,
            "author": self.author,
            "publisher": self.publisher,
            "reliability": self.reliability,
            "status": self.status,
            "verification_count": (
                self.verification_count
            ),
            "contradiction_count": (
                self.contradiction_count
            ),
            "tags": list(
                self.tags
            ),
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the source.
        """

        return asdict(
            self
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Source":
        """
        Restore a Source from serialized data.
        """

        return cls(
            id=str(
                data.get(
                    "id",
                    "",
                )
            ),
            title=str(
                data.get(
                    "title",
                    "",
                )
            ),
            source_type=str(
                data.get(
                    "source_type",
                    "unknown",
                )
            ),
            location=str(
                data.get(
                    "location",
                    "",
                )
            ),
            author=str(
                data.get(
                    "author",
                    "",
                )
            ),
            publisher=str(
                data.get(
                    "publisher",
                    "",
                )
            ),
            description=str(
                data.get(
                    "description",
                    "",
                )
            ),
            reliability=_clamp(
                data.get(
                    "reliability",
                    0.5,
                )
            ),
            status=str(
                data.get(
                    "status",
                    "unverified",
                )
            ),
            accessed_at=str(
                data.get(
                    "accessed_at",
                    _timestamp(),
                )
            ),
            published_at=data.get(
                "published_at"
            ),
            last_verified=data.get(
                "last_verified"
            ),
            verification_count=int(
                data.get(
                    "verification_count",
                    0,
                )
            ),
            contradiction_count=int(
                data.get(
                    "contradiction_count",
                    0,
                )
            ),
            tags=list(
                data.get(
                    "tags",
                    [],
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# SOURCE MANAGER
# ================================================================


class SourceManager:
    """
    Manages Mary's source registry.

    Responsibilities:

        - create sources
        - retrieve sources
        - update source trust
        - search sources
        - track verification
        - serialize source state

    It does not fetch external information.
    """

    def __init__(self) -> None:
        self.sources: dict[
            str,
            Source,
        ] = {}

    # ============================================================
    # CREATE
    # ============================================================

    def create(
        self,
        title: str,
        *,
        source_type: str = "unknown",
        location: str = "",
        author: str = "",
        publisher: str = "",
        description: str = "",
        reliability: float | None = None,
        status: str = "unverified",
        published_at: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Source:
        """
        Create and register a source.
        """

        source_type = str(
            source_type
        ).strip().lower()

        if source_type not in SOURCE_TYPES:
            source_type = "unknown"

        if reliability is None:
            reliability = (
                self.default_reliability(
                    source_type
                )
            )

        source = Source(
            id=self._next_id(),
            title=str(
                title
            ).strip(),
            source_type=source_type,
            location=str(
                location
            ).strip(),
            author=str(
                author
            ).strip(),
            publisher=str(
                publisher
            ).strip(),
            description=str(
                description
            ).strip(),
            reliability=reliability,
            status=status,
            published_at=published_at,
            tags=[
                str(tag).strip().lower()
                for tag in (
                    tags or []
                )
                if str(tag).strip()
            ],
            metadata=metadata or {},
        )

        self.sources[
            source.id
        ] = source

        return source

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        source_id: str,
    ) -> Source | None:
        """
        Retrieve a source.
        """

        return self.sources.get(
            source_id
        )

    def get_all(
        self,
    ) -> list[Source]:
        """
        Return all registered sources.
        """

        return list(
            self.sources.values()
        )

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
    ) -> list[Source]:
        """
        Perform a basic lexical search over source metadata.
        """

        query_words = _words(
            query
        )

        if not query_words:
            return []

        results: list[
            Source
        ] = []

        for source in self.sources.values():
            searchable = _words(
                " ".join(
                    [
                        source.title,
                        source.description,
                        source.author,
                        source.publisher,
                        source.location,
                        *source.tags,
                    ]
                )
            )

            if query_words & searchable:
                results.append(
                    source
                )

        results.sort(
            key=lambda item: item.reliability,
            reverse=True,
        )

        return results

    # ============================================================
    # FILTERS
    # ============================================================

    def by_type(
        self,
        source_type: str,
    ) -> list[Source]:
        """
        Return sources of a specific type.
        """

        source_type = str(
            source_type
        ).strip().lower()

        return [
            source
            for source in self.sources.values()
            if source.source_type
            == source_type
        ]

    def trusted(
        self,
        threshold: float = 0.75,
    ) -> list[Source]:
        """
        Return active sources above a reliability threshold.
        """

        threshold = _clamp(
            threshold
        )

        return [
            source
            for source in self.sources.values()
            if (
                source.status == "active"
                and source.reliability
                >= threshold
            )
        ]

    def active(
        self,
    ) -> list[Source]:
        """
        Return active sources.
        """

        return [
            source
            for source in self.sources.values()
            if source.status == "active"
        ]

    # ============================================================
    # VERIFICATION
    # ============================================================

    def verify(
        self,
        source_id: str,
        *,
        reliability: float | None = None,
    ) -> bool:
        """
        Verify a source.
        """

        source = self.get(
            source_id
        )

        if source is None:
            return False

        source.verify(
            reliability
        )

        return True

    def invalidate(
        self,
        source_id: str,
        *,
        reason: str = "",
    ) -> bool:
        """
        Invalidate a source.
        """

        source = self.get(
            source_id
        )

        if source is None:
            return False

        source.invalidate(
            reason
        )

        return True

    # ============================================================
    # CONTRADICTION TRACKING
    # ============================================================

    def record_contradiction(
        self,
        source_id: str,
    ) -> bool:
        """
        Record a contradiction associated with a source.
        """

        source = self.get(
            source_id
        )

        if source is None:
            return False

        source.record_contradiction()

        return True

    # ============================================================
    # DEFAULT RELIABILITY
    # ============================================================

    @staticmethod
    def default_reliability(
        source_type: str,
    ) -> float:
        """
        Provide a conservative baseline reliability based on source
        type.

        These are starting values, not claims that every source of
        a given type is trustworthy.
        """

        defaults = {
            "official": 0.90,
            "documentation": 0.85,
            "academic": 0.85,
            "government": 0.90,
            "book": 0.70,
            "experiment": 0.75,
            "creator": 0.85,
            "conversation": 0.65,
            "observation": 0.60,
            "web": 0.50,
            "system": 0.80,
            "unknown": 0.40,
        }

        return defaults.get(
            source_type,
            0.40,
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> list[dict[str, Any]]:
        """
        Serialize the entire source registry.
        """

        return [
            source.to_dict()
            for source in self.sources.values()
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore source registry from serialized data.
        """

        self.sources.clear()

        if not isinstance(
            data,
            list,
        ):
            return

        for entry in data:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            source = Source.from_dict(
                entry
            )

            if source.id:
                self.sources[
                    source.id
                ] = source

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_id(
        self,
    ) -> str:
        """
        Generate the next source ID.
        """

        highest = 0

        for source_id in self.sources:
            if not source_id.startswith(
                "source_"
            ):
                continue

            try:
                number = int(
                    source_id.split(
                        "_"
                    )[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return (
            f"source_{highest + 1}"
        )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
) -> float:
    """
    Keep a numeric value between 0.0 and 1.0.
    """

    try:
        value = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.5

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def _words(
    text: str,
) -> set[str]:
    """
    Normalize text into a set of words.
    """

    punctuation = (
        ".,!?;:\"'()[]{}"
    )

    return {
        word.strip(
            punctuation
        ).lower()
        for word in str(
            text
        ).split()
        if word.strip(
            punctuation
        )
    }


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()