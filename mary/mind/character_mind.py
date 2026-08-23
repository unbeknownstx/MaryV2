"""Mary's fast local character-mind coordinator.

This layer decides whether a turn can be handled by already represented local
state before invoking a language model.  It does not replace cognition; it is a
low-latency front porch to cognition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from time import monotonic
from typing import Any

from mary.cognition.intent import Intent
from .dialogue_policy import LocalDialoguePolicy
from .hot_state import HotMindState
from .local_composer import LocalResponseComposer
from .local_models import OllamaModelLab
from .reservoir import CognitiveReservoir
from .sources import authoritative_records


@dataclass(frozen=True)
class LocalMindResult:
    handled: bool
    response: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CharacterMind:
    def __init__(self, mary: Any, *, reservoir: CognitiveReservoir | None = None) -> None:
        self.mary = mary
        self.hot = HotMindState()
        self.reservoir = reservoir or CognitiveReservoir.in_memory()
        self.policy = LocalDialoguePolicy()
        self.composer = LocalResponseComposer()
        self.enabled = os.getenv("MARY_LOCAL_MIND_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
        self.local_dialogue_enabled = os.getenv("MARY_LOCAL_DIALOGUE_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
        self.last_result: dict[str, Any] = {}
        self.reservoir_dirty = False
        self.hot.refresh(mary)

    def configure_persistence(self, path: str | Path, *, rebuild: bool | None = None) -> None:
        old = self.reservoir
        max_records = int(os.getenv("MARY_RESERVOIR_MAX_RECORDS", "50000") or 50000)
        max_mb = int(os.getenv("MARY_RESERVOIR_MAX_MB", "512") or 512)
        self.reservoir = CognitiveReservoir(path, max_records=max_records, max_megabytes=max_mb)
        try:
            old.close()
        except Exception:
            pass
        should_rebuild = self.reservoir.status().get("records", 0) == 0 if rebuild is None else bool(rebuild)
        if should_rebuild:
            self.rebuild_reservoir()

    def configure_ephemeral(self, *, rebuild: bool = True) -> None:
        """Use an in-memory derived reservoir for temporary/test runtimes.

        This keeps release verification and other disposable MaryApplication
        instances from leaving SQLite file handles behind on Windows while
        preserving the exact same retrieval/authority semantics. Canonical
        desktop/runtime state continues to use the persistent reservoir by
        default.
        """
        old = self.reservoir
        self.reservoir = CognitiveReservoir.in_memory()
        try:
            old.close()
        except Exception:
            pass
        if rebuild:
            self.rebuild_reservoir()

    def close(self) -> None:
        """Release derived local-mind resources deterministically."""
        try:
            self.reservoir.close()
        except Exception:
            pass

    def rebuild_reservoir(self) -> int:
        count = self.reservoir.rebuild(authoritative_records(self.mary))
        self.reservoir_dirty = False
        return count

    def maintenance(self, *, force: bool = False) -> dict[str, Any]:
        """Refresh derived reservoir state outside the response-critical path."""
        rebuilt = 0
        if force or self.reservoir_dirty:
            rebuilt = self.rebuild_reservoir()
        return {"rebuilt": rebuilt, "dirty": self.reservoir_dirty, "reservoir": self.reservoir.status()}

    def refresh(self, *, rebuild_reservoir: bool = False) -> None:
        self.hot.refresh(self.mary)
        if rebuild_reservoir:
            self.rebuild_reservoir()

    def prompt_hits(self, text: str, *, limit: int = 5) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        hits = self.reservoir.search(text, limit=limit, minimum_confidence=0.65)
        return [
            {
                "content": hit.content,
                "kind": hit.kind,
                "authority": hit.authority,
                "confidence": round(hit.confidence, 3),
                "source": hit.source,
            }
            for hit in hits
        ]

    def try_respond(self, text: str, *, intent: Intent | None, context: dict[str, Any]) -> LocalMindResult:
        started = monotonic()
        if not self.enabled or not self.local_dialogue_enabled:
            return LocalMindResult(False, metadata={"reason": "local mind disabled"})
        # Explicitly injected test/custom routers retain their requested
        # cognition path. This keeps dependency-injection tests meaningful while
        # the canonical runtime still uses Mary's local reflex layer.
        try:
            provider_name = str(self.mary.llm.provider_name()).strip().lower()
        except Exception:
            provider_name = ""
        if provider_name in {"test", "fake", "mock"}:
            return LocalMindResult(False, metadata={"reason": "injected test router"})
        hot = self.hot.snapshot() or self.hot.refresh(self.mary)
        plan = self.policy.plan(text, intent=intent, hot_state=hot, reservoir=self.reservoir)
        if not plan.local:
            result = LocalMindResult(
                False,
                metadata={
                    "plan": plan.to_dict(),
                    "elapsed_ms": round((monotonic() - started) * 1000.0, 2),
                },
            )
            self.last_result = dict(result.metadata)
            return result
        response = self.composer.compose(plan, input_text=text, hot_state=hot).strip()
        handled = bool(response)
        result = LocalMindResult(
            handled,
            response=response,
            confidence=plan.confidence if handled else 0.0,
            metadata={
                "plan": plan.to_dict(),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 2),
                "reservoir_records": self.reservoir.status().get("records", 0),
                "local_only": True,
            },
        )
        self.last_result = dict(result.metadata)
        return result

    def observe_completed_turn(self, result: Any) -> None:
        """Refresh cheap state after a turn; rebuild only after represented learning."""
        metadata = dict(getattr(result, "metadata", {}) or {})
        system_action = str(metadata.get("system_action") or "").strip().lower()
        learned = bool(
            metadata.get("natural_relationship_learning")
            or metadata.get("shared_work_learning")
            or system_action in {
                "memory_store", "relationship_share", "creator_directive",
                "remember", "remember_fact", "remember_event",
            }
        )
        # Keep the cheap RAM projection current immediately, but defer the
        # potentially larger derived-index rebuild until idle/close/explicit
        # maintenance so learning does not extend perceived response latency.
        self.refresh(rebuild_reservoir=False)
        if learned:
            self.reservoir_dirty = True

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "local_dialogue_enabled": self.local_dialogue_enabled,
            "hot": self.hot.status(),
            "reservoir": self.reservoir.status(),
            "last_local_decision": dict(self.last_result),
            "reservoir_dirty": bool(self.reservoir_dirty),
            "local_model_catalog": OllamaModelLab.catalog(),
            "semantics": "rebuildable local projection; canonical Mary state remains authoritative",
        }
