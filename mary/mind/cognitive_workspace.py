"""MaryV2 cognitive blackboard / global workspace projection.

This is the connective layer between existing authorities.  It owns no identity,
memory, relationship, world truth, plan execution, tool permission or model
weights.  For one query/task it builds a bounded typed working set containing:
- canonical/self state references,
- relevant durable memory,
- authored character evidence,
- current world-model beliefs and uncertainty,
- relevant approved procedural skills,
- active executive plans / next actions,
- available compute capabilities,
- locally owned knowledge-pack routes.

The snapshot is disposable and rebuildable.  This keeps model context coherent
without creating another canonical database.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .context_governor import ContextEvidenceGovernor


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_call(fn, default):
    try:
        return fn()
    except Exception:
        return default


def _clip(value: Any, limit: int = 800) -> str:
    return " ".join(str(value or "").split())[:limit]


@dataclass(frozen=True)
class CognitiveWorkspaceSnapshot:
    query: str
    generated_at: str
    identity: dict[str, Any]
    memory: dict[str, Any]
    character: dict[str, Any]
    world: dict[str, Any]
    skills: dict[str, Any]
    plans: dict[str, Any]
    compute: dict[str, Any]
    knowledge: dict[str, Any]
    epistemic: dict[str, Any]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CognitiveWorkspace:
    """Build Mary Core's bounded shared working set for reasoning/delegation."""

    VERSION = 1

    def __init__(self, mary: Any) -> None:
        self.mary = mary
        self.context_governor = ContextEvidenceGovernor()

    def build(
        self,
        query: str,
        *,
        memory_limit: int = 6,
        character_limit: int = 5,
        belief_limit: int = 10,
        skill_limit: int = 6,
        plan_limit: int = 6,
        knowledge_limit: int = 6,
    ) -> CognitiveWorkspaceSnapshot:
        query = _clip(query, 2000)

        node_state = _safe_call(lambda: dict(self.mary.node_registry.snapshot() or {}), {})
        capabilities, permissions, nodes = self._node_capabilities(node_state)
        connected_node_ids = {
            str(node.get("node_id") or "")
            for node in nodes
            if bool(node.get("connected")) and str(node.get("node_id") or "")
        }
        competence_records = _safe_call(
            lambda: list(self.mary.competence.find(limit=80)),
            [],
        )
        demonstrated = [
            {
                "capability": item.capability,
                "operation": item.operation,
                "node_id": item.node_id,
                "skill_id": item.skill_id,
                "attempts": item.attempts,
                "successes": item.successes,
                "failures": item.failures,
                "verified_successes": item.verified_successes,
                "reliability": item.reliability,
                "evidence_strength": item.evidence_strength,
                "mean_latency_ms": item.mean_latency_ms,
                "last_success": item.last_success,
                "last_observed_at": item.last_observed_at,
            }
            for item in competence_records
            if item.capability in capabilities
            and (not item.node_id or item.node_id in connected_node_ids)
        ][:16]

        memory_hits = _safe_call(
            lambda: list(self.mary.memory.recall(query, limit=max(1, min(12, int(memory_limit))))),
            [],
        )
        memory_hits = [self._bounded_mapping(item, 12) for item in memory_hits[:memory_limit]]
        memory_status = _safe_call(lambda: dict(self.mary.memory.status() or {}), {})

        selection = _safe_call(
            lambda: self.mary.character_sourcebook.select(
                query,
                limit=max(1, min(12, int(character_limit))),
                max_characters=4200,
            ),
            None,
        )
        character_records: list[dict[str, Any]] = []
        if selection is not None:
            for record in list(getattr(selection, "records", ()) or ())[:character_limit]:
                character_records.append({
                    "record_id": str(getattr(record, "record_id", "")),
                    "heading": _clip(getattr(record, "heading", ""), 240),
                    "text": _clip(getattr(record, "text", ""), 1200),
                    "labels": [
                        str(item)
                        for item in list(getattr(record, "labels", ()) or ())[:8]
                    ],
                    "source": _clip(getattr(record, "source_name", ""), 180),
                    "provenance": _clip(getattr(record, "provenance", ""), 180),
                })

        beliefs = _safe_call(
            lambda: list(self.mary.world_model.relevant(query, limit=belief_limit)),
            [],
        )
        world_rows = [
            {
                "id": item.id,
                "subject": item.subject,
                "predicate": item.predicate,
                "value": item.value,
                "belief_type": item.belief_type,
                "status": item.status,
                "confidence": item.confidence,
                "source": item.source,
                "authority": item.authority,
                "verification": item.verification,
                "evidence_ids": list(item.evidence_ids),
            }
            for item in beliefs[:belief_limit]
        ]

        replay_episodes = _safe_call(
            lambda: list(self.mary.experience_replay.similar(query, limit=4)),
            [],
        )
        replay_lessons = _safe_call(
            lambda: list(self.mary.experience_replay.lessons(limit=4)),
            [],
        )

        skills = _safe_call(
            lambda: list(self.mary.procedural_skills.retrieve(
                query,
                capabilities=capabilities,
                permissions=permissions,
                limit=skill_limit,
                approved_only=True,
            )),
            [],
        )
        skill_rows = [
            {
                "id": item.id,
                "name": item.name,
                "version": item.version,
                "description": item.description,
                "confidence": item.confidence,
                "success_count": item.success_count,
                "failure_count": item.failure_count,
                "required_capabilities": list(item.required_capabilities),
                "required_permissions": list(item.required_permissions),
                "preconditions": list(item.preconditions),
                "steps": list(item.steps),
                "verification": list(item.verification),
                "failure_recovery": list(item.failure_recovery),
            }
            for item in skills[:skill_limit]
        ]

        relevant_plans = _safe_call(
            lambda: list(self.mary.executive_plans.relevant(query, limit=plan_limit)),
            [],
        )
        next_actions = _safe_call(
            lambda: list(self.mary.executive_plans.next_actions(
                available_capabilities=capabilities,
                granted_approvals=permissions,
                limit=plan_limit,
            )),
            [],
        )
        plan_rows = [
            {
                "id": plan.id,
                "objective": plan.objective,
                "status": plan.status,
                "priority": plan.priority,
                "goal_id": plan.goal_id,
                "workflow_id": plan.workflow_id,
                "tags": list(plan.tags),
                "progress": {
                    "completed": sum(1 for step in plan.steps if step.status == "completed"),
                    "total": len(plan.steps),
                },
                "blockers": list(dict.fromkeys(
                    blocker
                    for step in plan.steps
                    for blocker in step.blockers
                ))[:12],
            }
            for plan in relevant_plans[:plan_limit]
        ]

        knowledge_routes = _safe_call(
            lambda: list(self.mary.knowledge_fabric.plan(query, limit=knowledge_limit)),
            [],
        )
        route_pack_ids = [
            str(item.get("pack_id") or "")
            for item in knowledge_routes[:knowledge_limit]
            if str(item.get("pack_id") or "")
        ]
        knowledge_hits = _safe_call(
            lambda: list(
                self.mary.knowledge_fabric.search(
                    query,
                    pack_ids=route_pack_ids,
                    limit=knowledge_limit,
                )
            )
            if route_pack_ids
            else [],
            [],
        )
        knowledge_status = _safe_call(lambda: dict(self.mary.knowledge_fabric.status() or {}), {})
        knowledge_evidence_rows = [
            {
                "pack_id": item.pack_id,
                "title": _clip(item.title, 240),
                "snippet": _clip(item.snippet, 1200),
                "source": _clip(item.source, 300),
                "score": item.score,
                "locator": _clip(item.locator, 500),
                "content_hash": _clip(item.content_hash, 128),
            }
            for item in knowledge_hits[:knowledge_limit]
        ]

        # The workspace can retrieve more evidence than a small local model should
        # see in one prompt.  Govern only model-facing candidate records; owning
        # stores retain every omitted item and their authority semantics.
        governed, context_budget_report = self.context_governor.govern({
            "world": world_rows,
            "plans": plan_rows,
            "skills": skill_rows,
            "compute": demonstrated,
            "knowledge": knowledge_evidence_rows,
        })
        world_rows = governed.get("world", [])
        plan_rows = governed.get("plans", [])
        skill_rows = governed.get("skills", [])
        demonstrated = governed.get("compute", [])
        knowledge_evidence_rows = governed.get("knowledge", [])

        identity = {
            "name": str(getattr(self.mary.identity, "name", "Mary") or "Mary"),
            "authority": "Mary Core canonical identity",
            "lifecycle": _safe_call(lambda: str(self.mary.lifecycle.state.value), "unknown"),
            "self_model": self._bounded_mapping(
                _safe_call(lambda: dict(self.mary.self_model.to_dict() or {}), {}),
                16,
            ),
        }

        epistemic = _safe_call(lambda: dict(self.mary.world_model.epistemic_summary() or {}), {})
        epistemic.update({
            "memory_hits_are_candidates": True,
            "character_sourcebook_is_authored_authority": True,
            "world_beliefs_may_be_contested": any(
                row.get("status") == "contested" for row in world_rows
            ),
            "knowledge_hits_are_evidence_not_memory": True,
            "plans_do_not_authorize_actions": True,
        })

        return CognitiveWorkspaceSnapshot(
            query=query,
            generated_at=_now(),
            identity=identity,
            memory={
                "counts": dict(memory_status.get("counts") or {}),
                "relevant": memory_hits,
                "authority": "MemoryManager",
            },
            character={
                "records": character_records,
                "sourcebook_hash": str(
                    getattr(self.mary.character_sourcebook, "sourcebook_hash", "")
                ),
                "authority": "creator-authored character evidence",
            },
            world={
                "beliefs": world_rows,
                "status": _safe_call(lambda: dict(self.mary.world_model.status() or {}), {}),
                "authority": "WorldModel evidence layer",
            },
            skills={
                "eligible": skill_rows,
                "replay": [
                    {
                        "id": item.id,
                        "capability": item.capability,
                        "operation": item.operation,
                        "success": item.success,
                        "verified": item.verified,
                        "outcome": _clip(item.outcome_summary, 500),
                        "tags": list(item.tags),
                    }
                    for item in replay_episodes[:4]
                ],
                "lessons": [
                    {
                        "id": item.id,
                        "type": item.lesson_type,
                        "summary": _clip(item.summary, 600),
                        "success_rate": item.success_rate,
                        "confidence": item.confidence,
                        "status": item.status,
                    }
                    for item in replay_lessons[:4]
                ],
                "status": _safe_call(lambda: dict(self.mary.procedural_skills.status() or {}), {}),
                "replay_status": _safe_call(lambda: dict(self.mary.experience_replay.status() or {}), {}),
                "authority": (
                    "procedural know-how/replay evidence only; "
                    "capability fabric executes and creator approves skills"
                ),
            },
            plans={
                "active": plan_rows,
                "next_actions": next_actions[:plan_limit],
                "status": _safe_call(lambda: dict(self.mary.executive_plans.status() or {}), {}),
                "authority": "explicit progress state; not hidden reasoning",
            },
            compute={
                "connected_nodes": sum(1 for node in nodes if bool(node.get("connected"))),
                "registered_nodes": len(nodes),
                "capabilities": sorted(capabilities)[:120],
                "authorized_capabilities": sorted(permissions)[:120],
                "demonstrated": demonstrated,
                "competence_status": _safe_call(
                    lambda: dict(self.mary.competence.status() or {}),
                    {},
                ),
                "semantics": (
                    "capabilities are current advertisements; demonstrated entries "
                    "are durable measured evidence and remain non-authoritative"
                ),
                "authority": "replaceable workers; Mary state remains Core-owned",
            },
            knowledge={
                "routes": knowledge_routes[:knowledge_limit],
                "evidence": knowledge_evidence_rows,
                "status": knowledge_status,
                "authority": (
                    "retrieved evidence substrate only; hits are not memory, "
                    "identity, relationship facts or automatic world truth"
                ),
            },
            epistemic=epistemic,
            policy={
                "version": self.VERSION,
                "persistent": False,
                "rebuildable": True,
                "hidden_chain_of_thought": False,
                "identity_owner": False,
                "memory_owner": False,
                "tool_authority": False,
                "context_budget": context_budget_report,
                "purpose": "bind the smallest relevant cross-system working set for cognition",
            },
        )

    @staticmethod
    def _node_capabilities(snapshot: dict[str, Any]) -> tuple[set[str], set[str], list[dict[str, Any]]]:
        nodes = [
            dict(item)
            for item in list(snapshot.get("nodes") or [])
            if isinstance(item, dict)
        ]
        capabilities: set[str] = set()
        authorized: set[str] = set()
        for node in nodes:
            if not bool(node.get("connected")):
                continue
            for name, raw in dict(node.get("capabilities") or {}).items():
                info = dict(raw or {}) if isinstance(raw, dict) else {}
                if not bool(info.get("available", True)):
                    continue
                capabilities.add(str(name))
                metadata = dict(info.get("metadata") or {})
                if bool(info.get("execution_authorized")) or bool(metadata.get("execution_authorized")):
                    authorized.add(str(name))
        return capabilities, authorized, nodes

    @staticmethod
    def _bounded_mapping(value: Any, limit: int) -> dict[str, Any]:
        if not isinstance(value, dict):
            if hasattr(value, "to_dict"):
                try:
                    value = value.to_dict()
                except Exception:
                    value = {"value": str(value)}
            else:
                value = {"value": str(value)}
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:limit]:
            name = _clip(key, 80)
            if not name:
                continue
            if isinstance(item, str):
                output[name] = _clip(item, 800)
            elif isinstance(item, (int, float, bool)) or item is None:
                output[name] = item
            elif isinstance(item, (list, tuple)):
                output[name] = [
                    _clip(entry, 240) if not isinstance(entry, (int, float, bool)) else entry
                    for entry in list(item)[:12]
                ]
            else:
                output[name] = _clip(item, 800)
        return output
