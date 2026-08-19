"""MaryV2 orchestration task data models.

These models describe temporary work Mary performs while solving a task.
They are intentionally separate from Mary's durable memory, creator model,
personality, and developed-self state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class TaskStatus(str, Enum):
    """Lifecycle states for one ephemeral orchestration task."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProvenanceSource(str, Enum):
    """Known origins for temporary task evidence.

    A source label records where a claim/result came from. It does not imply
    that the source is correct or that the information is safe to persist.
    """

    CREATOR = "creator"
    MARY_RUNTIME = "mary_runtime"
    PERSISTENT_MEMORY = "persistent_memory"
    RELATIONSHIP_MODEL = "relationship_model"
    LOCAL_TOOL = "local_tool"
    TEST_RESULT = "test_result"
    WEB = "web"
    GROQ = "groq"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    OPENAI = "openai"
    INFERENCE = "inference"


@dataclass(frozen=True)
class TaskEvidence:
    """One temporary claim, observation, or result available to a task."""

    evidence_id: str
    content: str
    provenance: str
    source_detail: str = ""
    confidence: float = 0.5
    created_at: str = field(default_factory=_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", str(self.content).strip())
        object.__setattr__(self, "provenance", str(self.provenance).strip().lower())
        object.__setattr__(self, "source_detail", str(self.source_detail).strip())
        object.__setattr__(self, "confidence", _clamp(self.confidence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskHypothesis:
    """A temporary idea to test; never durable self-state by itself."""

    hypothesis_id: str
    content: str
    status: str = "open"
    confidence: float = 0.5
    created_at: str = field(default_factory=_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", str(self.content).strip())
        object.__setattr__(self, "status", str(self.status).strip().lower() or "open")
        object.__setattr__(self, "confidence", _clamp(self.confidence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskConsultation:
    """A recorded specialist/model consultation result.

    Consultation output is evidence for Mary to evaluate, not authoritative
    truth and not a direct mutation path into any durable subsystem.
    """

    consultation_id: str
    role: str
    source: str
    request_summary: str
    response_summary: str
    status: str = "completed"
    created_at: str = field(default_factory=_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", str(self.role).strip().lower())
        object.__setattr__(self, "source", str(self.source).strip().lower())
        object.__setattr__(self, "request_summary", str(self.request_summary).strip())
        object.__setattr__(self, "response_summary", str(self.response_summary).strip())
        object.__setattr__(self, "status", str(self.status).strip().lower() or "completed")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskDecisionRecord:
    """A task-local decision record, separate from Agency.DecisionSystem."""

    decision_id: str
    description: str
    reason: str = ""
    status: str = "proposed"
    created_at: str = field(default_factory=_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "description", str(self.description).strip())
        object.__setattr__(self, "reason", str(self.reason).strip())
        object.__setattr__(self, "status", str(self.status).strip().lower() or "proposed")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "TaskStatus",
    "ProvenanceSource",
    "TaskEvidence",
    "TaskHypothesis",
    "TaskConsultation",
    "TaskDecisionRecord",
]
