"""
MaryV2 - Researcher

Responsible for coordinating research requests.

The researcher does not permanently store knowledge and does not
directly modify Mary's personality, memory, or beliefs.

Architecture:

    Curiosity / Question / Goal
                ↓
            Researcher
                ↓
          Research Request
                ↓
            Web Tool
                ↓
             Sources
                ↓
            Evaluator
                ↓
        Knowledge / Memory
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# ================================================================
# RESEARCH DATA
# ================================================================


@dataclass
class ResearchRequest:
    """
    Represents a request for information.

    A request describes what Mary wants to investigate without
    assuming how the information will be obtained.
    """

    id: str

    query: str

    purpose: str = ""

    status: str = "pending"

    priority: float = 0.5

    source_limit: int = 5

    created_at: str = ""

    completed_at: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()

        self.priority = _clamp(
            self.priority
        )

        if self.source_limit < 1:
            self.source_limit = 1


# ================================================================
# RESEARCH SOURCE
# ================================================================


@dataclass
class ResearchSource:
    """
    Represents a source discovered during research.

    The researcher records the source.

    The evaluator determines how trustworthy or useful it is.
    """

    id: str

    title: str

    url: str = ""

    content: str = ""

    source_type: str = "web"

    relevance: float = 0.5

    confidence: float = 0.5

    retrieved_at: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.retrieved_at:
            self.retrieved_at = _timestamp()

        self.relevance = _clamp(
            self.relevance
        )

        self.confidence = _clamp(
            self.confidence
        )


# ================================================================
# RESEARCH RESULT
# ================================================================


@dataclass
class ResearchResult:
    """
    Collection of information returned from a research request.
    """

    request_id: str

    query: str

    sources: list[ResearchSource] = field(
        default_factory=list
    )

    summary: str = ""

    status: str = "completed"

    created_at: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _timestamp()


# ================================================================
# RESEARCHER
# ================================================================


class Researcher:
    """
    Mary's research coordination system.

    This class deliberately does not contain HTTP or browser code.

    Actual external access should eventually happen through:

        mary.tools.web

    This separation allows the web implementation to change without
    rewriting Mary's learning architecture.
    """

    def __init__(
        self,
        web_tool: Any | None = None,
    ) -> None:
        self.web_tool = web_tool

        self.requests: list[
            ResearchRequest
        ] = []

        self.results: list[
            ResearchResult
        ] = []

    # ============================================================
    # REQUEST CREATION
    # ============================================================

    def create_request(
        self,
        query: str,
        *,
        purpose: str = "",
        priority: float = 0.5,
        source_limit: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchRequest:
        """
        Create a new research request.
        """

        request = ResearchRequest(
            id=self._next_request_id(),
            query=str(
                query
            ).strip(),
            purpose=str(
                purpose
            ).strip(),
            priority=priority,
            source_limit=source_limit,
            metadata=metadata or {},
        )

        self.requests.append(
            request
        )

        return request

    # ============================================================
    # REQUEST ACCESS
    # ============================================================

    def get_request(
        self,
        request_id: str,
    ) -> ResearchRequest | None:
        """
        Retrieve a research request.
        """

        for request in self.requests:
            if request.id == request_id:
                return request

        return None

    def get_pending_requests(
        self,
    ) -> list[ResearchRequest]:
        """
        Return pending research requests.
        """

        return [
            request
            for request in self.requests
            if request.status == "pending"
        ]

    def get_requests(
        self,
    ) -> list[ResearchRequest]:
        """
        Return all research requests.
        """

        return list(
            self.requests
        )

    # ============================================================
    # RESEARCH
    # ============================================================

    def research(
        self,
        request: ResearchRequest,
    ) -> ResearchResult:
        """
        Execute a research request through the configured tool.

        If no web tool is configured, the method safely returns an
        empty result instead of pretending that research occurred.
        """

        request.status = "researching"

        raw_results: Any = []

        if self.web_tool is not None:
            raw_results = self._query_web_tool(
                request
            )

        return self.complete_with_sources(
            request,
            raw_results,
        )

    def complete_with_sources(
        self,
        request: ResearchRequest,
        raw_results: Any,
        *,
        status: str = "completed",
    ) -> ResearchResult:
        """
        Complete a research request from externally obtained sources.

        This is the preferred bridge when another subsystem (for example
        ToolRegistry) owns permission and execution. Researcher normalizes
        and records sources but does not bypass that external boundary.
        """

        request.status = "researching"

        sources = self._normalize_sources(
            raw_results
        )

        result = ResearchResult(
            request_id=request.id,
            query=request.query,
            sources=sources,
            status=status,
        )

        self.results.append(
            result
        )

        request.status = status
        request.completed_at = _timestamp()

        return result

    # ============================================================
    # WEB TOOL ADAPTER
    # ============================================================

    def _query_web_tool(
        self,
        request: ResearchRequest,
    ) -> list[ResearchSource]:
        """
        Adapt different web-tool interfaces into ResearchSource
        objects.

        Supported future tool styles can return:

            list[dict]

            list[ResearchSource]

            dict containing "results"

        The researcher remains independent from the concrete web
        implementation.
        """

        try:
            if hasattr(
                self.web_tool,
                "search",
            ):
                raw_results = (
                    self.web_tool.search(
                        request.query,
                        limit=request.source_limit,
                    )
                )

            elif callable(
                self.web_tool
            ):
                raw_results = (
                    self.web_tool(
                        request.query
                    )
                )

            else:
                return []

        except Exception:
            request.status = "failed"
            return []

        return self._normalize_sources(
            raw_results
        )

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_sources(
        self,
        raw_results: Any,
    ) -> list[ResearchSource]:
        """
        Convert external search results into Mary's internal
        ResearchSource representation.
        """

        if raw_results is None:
            return []

        if isinstance(
            raw_results,
            dict,
        ):
            raw_results = raw_results.get(
                "results",
                [],
            )

        if not isinstance(
            raw_results,
            (list, tuple),
        ):
            return []

        sources: list[
            ResearchSource
        ] = []

        for index, item in enumerate(
            raw_results,
            start=1,
        ):
            if isinstance(
                item,
                ResearchSource,
            ):
                sources.append(
                    item
                )
                continue

            to_dict = getattr(
                item,
                "to_dict",
                None,
            )

            if callable(to_dict):
                converted = to_dict()
                if isinstance(converted, dict):
                    item = converted

            elif (
                not isinstance(item, (str, dict))
                and hasattr(item, "title")
            ):
                item = {
                    "title": getattr(item, "title", ""),
                    "url": getattr(item, "url", ""),
                    "snippet": getattr(item, "snippet", ""),
                    "metadata": getattr(item, "metadata", {}),
                }

            if isinstance(
                item,
                str,
            ):
                sources.append(
                    ResearchSource(
                        id=(
                            f"source_{index}"
                        ),
                        title=item,
                    )
                )

                continue

            if not isinstance(
                item,
                dict,
            ):
                continue

            title = str(
                item.get(
                    "title",
                    item.get(
                        "name",
                        f"Source {index}",
                    ),
                )
            )

            url = str(
                item.get(
                    "url",
                    item.get(
                        "link",
                        "",
                    ),
                )
            )

            content = str(
                item.get(
                    "content",
                    item.get(
                        "snippet",
                        item.get(
                            "text",
                            "",
                        ),
                    ),
                )
            )

            source = ResearchSource(
                id=str(
                    item.get(
                        "id",
                        f"source_{index}",
                    )
                ),
                title=title,
                url=url,
                content=content,
                source_type=str(
                    item.get(
                        "source_type",
                        "web",
                    )
                ),
                relevance=_clamp(
                    item.get(
                        "relevance",
                        0.5,
                    )
                ),
                confidence=_clamp(
                    item.get(
                        "confidence",
                        0.5,
                    )
                ),
                metadata=item.get(
                    "metadata",
                    {},
                ),
            )

            sources.append(
                source
            )

        return sources

    # ============================================================
    # RESULTS
    # ============================================================

    def get_result(
        self,
        request_id: str,
    ) -> ResearchResult | None:
        """
        Retrieve the result associated with a request.
        """

        for result in reversed(
            self.results
        ):
            if result.request_id == request_id:
                return result

        return None

    def get_results(
        self,
    ) -> list[ResearchResult]:
        """
        Return all research results.
        """

        return list(
            self.results
        )

    # ============================================================
    # SOURCE FILTERING
    # ============================================================

    def get_relevant_sources(
        self,
        result: ResearchResult,
        minimum_relevance: float = 0.5,
    ) -> list[ResearchSource]:
        """
        Return sources above the requested relevance threshold.
        """

        minimum_relevance = _clamp(
            minimum_relevance
        )

        return [
            source
            for source in result.sources
            if source.relevance
            >= minimum_relevance
        ]

    def get_high_confidence_sources(
        self,
        result: ResearchResult,
        minimum_confidence: float = 0.7,
    ) -> list[ResearchSource]:
        """
        Return sources above the requested confidence threshold.
        """

        minimum_confidence = _clamp(
            minimum_confidence
        )

        return [
            source
            for source in result.sources
            if source.confidence
            >= minimum_confidence
        ]

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize research state.
        """

        return {
            "requests": [
                asdict(request)
                for request in self.requests
            ],
            "results": [
                asdict(result)
                for result in self.results
            ],
        }

    def from_dict(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Restore research state.
        """

        self.requests.clear()
        self.results.clear()

        if not isinstance(
            data,
            dict,
        ):
            return

        requests = data.get(
            "requests",
            [],
        )

        if isinstance(
            requests,
            list,
        ):
            for entry in requests:
                if not isinstance(
                    entry,
                    dict,
                ):
                    continue

                request = ResearchRequest(
                    id=str(
                        entry.get(
                            "id",
                            "",
                        )
                    ),
                    query=str(
                        entry.get(
                            "query",
                            "",
                        )
                    ),
                    purpose=str(
                        entry.get(
                            "purpose",
                            "",
                        )
                    ),
                    status=str(
                        entry.get(
                            "status",
                            "pending",
                        )
                    ),
                    priority=_clamp(
                        entry.get(
                            "priority",
                            0.5,
                        )
                    ),
                    source_limit=int(
                        entry.get(
                            "source_limit",
                            5,
                        )
                    ),
                    created_at=str(
                        entry.get(
                            "created_at",
                            _timestamp(),
                        )
                    ),
                    completed_at=entry.get(
                        "completed_at"
                    ),
                    metadata=entry.get(
                        "metadata",
                        {},
                    ),
                )

                self.requests.append(
                    request
                )

        results = data.get(
            "results",
            [],
        )

        if isinstance(
            results,
            list,
        ):
            for entry in results:
                if not isinstance(
                    entry,
                    dict,
                ):
                    continue

                raw_sources = entry.get(
                    "sources",
                    [],
                )

                sources = (
                    self._normalize_sources(
                        raw_sources
                    )
                )

                result = ResearchResult(
                    request_id=str(
                        entry.get(
                            "request_id",
                            "",
                        )
                    ),
                    query=str(
                        entry.get(
                            "query",
                            "",
                        )
                    ),
                    sources=sources,
                    summary=str(
                        entry.get(
                            "summary",
                            "",
                        )
                    ),
                    status=str(
                        entry.get(
                            "status",
                            "completed",
                        )
                    ),
                    created_at=str(
                        entry.get(
                            "created_at",
                            _timestamp(),
                        )
                    ),
                    metadata=entry.get(
                        "metadata",
                        {},
                    ),
                )

                self.results.append(
                    result
                )

    # ============================================================
    # ID GENERATION
    # ============================================================

    def _next_request_id(
        self,
    ) -> str:
        """
        Generate the next research request ID.
        """

        highest = 0

        for request in self.requests:
            request_id = str(
                request.id
            )

            if not request_id.startswith(
                "research_"
            ):
                continue

            try:
                number = int(
                    request_id.split(
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
            f"research_{highest + 1}"
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
        value = float(value)
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


def _timestamp() -> str:
    """
    Return a timezone-aware UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()