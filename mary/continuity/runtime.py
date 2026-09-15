"""MaryV2 13.4 Experiential Continuity composition root."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .cancellation import GenerationCancellationRegistry
from .experience import ExperienceLedger
from .lanes import CognitionLaneRouter
from .memory_lab import MemoryEvaluationSuite
from .prosody import TurnTakingAdvisor
from .recovery import NodeRecoveryManager
from .resources import AffordanceScorer, ComputeResourceGovernor
from .skills import SkillLibrary
from .temporal import TemporalKnowledgeGraph
from .trace import CausalTraceLedger
from .verification import ActionVerificationManager
from .workflows import DurableWorkflowStore


class ExperientialContinuityRuntime:
    """Connect experience, temporal truth, skills, checkpoints and verification.

    The runtime deliberately owns no identity/personality/relationship truth and
    has no tool execution authority. It provides durable continuity evidence and
    operational coordination around Mary's existing canonical owners.
    """

    VERSION = "13.4"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.experience = ExperienceLedger(self.root / "experience.json")
        self.cognition_lanes = CognitionLaneRouter()
        self.cancellation = GenerationCancellationRegistry()
        self.memory_lab = MemoryEvaluationSuite()
        self.temporal = TemporalKnowledgeGraph(self.root / "temporal_knowledge.json")
        self.skills = SkillLibrary(self.root / "skills.json")
        self.workflows = DurableWorkflowStore(self.root / "workflows.json")
        self.verification = ActionVerificationManager(self.root / "verification.json")
        self.resources = ComputeResourceGovernor(self.root / "resources.json")
        self.node_recovery = NodeRecoveryManager(self.root / "node_recovery.json")
        self.affordances = AffordanceScorer()
        self.prosody = TurnTakingAdvisor()
        self.traces = CausalTraceLedger(self.root / "traces.json")

    def dream_cycle(self) -> dict[str, Any]:
        """Run safe idle-time consolidation; candidates never self-promote."""
        return self.maintenance()

    def maintenance(self) -> dict[str, Any]:
        candidates = self.experience.consolidate()
        return {
            "version": self.VERSION,
            "experience_candidates_created": len(candidates),
            "resumable_workflows": len(self.workflows.resumable()),
            "pending_verifications": len(self.verification.pending()),
            "promotion_performed": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "experience": self.experience.status(),
            "temporal": self.temporal.status(),
            "skills": self.skills.status(),
            "workflows": self.workflows.status(),
            "verification": self.verification.status(),
            "resources": self.resources.status(),
            "node_recovery": self.node_recovery.status(),
            "cognition_lanes": self.cognition_lanes.status(),
            "cancellation": self.cancellation.status(),
            "memory_lab": {"version": self.memory_lab.VERSION, "cases": len(self.memory_lab.default_cases())},
            "traces": self.traces.status(),
            "authority": {
                "identity": False,
                "memory": False,
                "relationship": False,
                "tool_execution": False,
                "autonomy_permission": False,
            },
        }
