"""
MaryV2 - Mary Core

Top-level coordinator for Mary's systems.

Mary connects the major subsystems while allowing each subsystem
to remain responsible for its own behavior.

Core process flow:

    Input
      ↓
    Context
      ↓
    Intent
      ↓
    Intent-specific system action
      ↓
    Cognition
      ↓
    Response

Mary coordinates systems.

Mary does not replace:
    - cognition
    - memory
    - personality
    - learning
    - relationships
    - LLM routing
"""

from __future__ import annotations

import json
import re
from typing import Any

from mary.core.config import Config
from mary.core.identity import Identity
from mary.core.lifecycle import Lifecycle

from mary.agency.agency import Agency
from mary.autonomy.runtime import AutonomyRuntime

from mary.conversation.service import ConversationService

from mary.expression.dialogue import DialogueManager
from mary.expression.emotion import EmotionManager
from mary.expression.response import ResponseBuilder
from mary.expression.expression import ExpressionSystem

from mary.avatar.bridge import AvatarBridge

from mary.audio import (
    AudioManager,
    NullAudioInputProvider,
    NullAudioOutputProvider,
    create_audio_input_service,
    create_audio_output_service,
)

from mary.identity.biography import create_default_biography
from mary.identity.self_model import SelfModel

from mary.personality.personality import Personality
from mary.personality.development import PersonalityDevelopment
from mary.personality.character import Character
from mary.personality.values import Values

from mary.relationship.manager import RelationshipManager
from mary.relationship.directives import CreatorDirectiveSystem
from mary.relationship.curiosity_development import RelationshipCuriosityDevelopment

from mary.learning.learner import Learner
from mary.learning.evaluator import Evaluator
from mary.learning.researcher import Researcher
from mary.learning.grounding import ResearchGrounder
from mary.learning.source_resolver import SourceResolver
from mary.learning.evidence import ClaimGrounder, EvidenceValidator

from mary.tools.manager import ToolManager
from mary.tools.registry import PermissionLevel

from mary.knowledge.manager import KnowledgeManager

from mary.memory.manager import MemoryManager

from mary.cognition.orchestrator import (
    CognitiveCycleResult,
    CognitiveOrchestrator,
)
from mary.cognition.reasoning import ReasoningEngine, ReasoningResult
from mary.cognition.reflection import (
    ReflectionDecision,
    ReflectionEngine,
    ReflectionResult,
)
from mary.cognition.context import CognitiveContext
from mary.cognition.code_change import CodeChangePlanner
from mary.cognition.self_introspection import SelfIntrospection
from mary.cognition.intent import Intent, IntentType


class Mary:
    """
    Top-level coordinator for MaryV2.

    Mary owns subsystem instances and coordinates communication
    between them.

    Subsystems remain responsible for their own internal behavior.
    """

    def __init__(self) -> None:

        # ============================================================
        # CONFIGURATION
        # ============================================================

        self.config = Config()

        # ============================================================
        # LIFECYCLE
        # ============================================================

        self.lifecycle = Lifecycle()

        self.lifecycle.initialize()
        self.lifecycle.ready()

        # ============================================================
        # IDENTITY
        # ============================================================

        self.identity = Identity()

        # ============================================================
        # PERSONALITY
        # ============================================================

        self.personality = Personality(
            name="Mary",
        )

        self.personality_development = PersonalityDevelopment(
            personality=self.personality,
        )

        # ============================================================
        # CHARACTER
        # ============================================================

        self.character = Character()

        # ============================================================
        # VALUES
        # ============================================================

        self.values = Values()

        # ============================================================
        # SELF MODEL
        # ============================================================

        self.self_model = SelfModel(
            name="Mary",
            personality=self.personality,
            character=self.character,
            values=self.values,
        )

        # ============================================================
        # BIOGRAPHY
        # ============================================================

        self.biography = create_default_biography()

        # ============================================================
        # RELATIONSHIP
        # ============================================================

        self.relationship = RelationshipManager()
        self.relationship.load()

        # Keep one authoritative creator model and expose the existing
        # relationship components through Mary for compatibility.
        self.user_model = self.relationship.user_model
        self.relationship_history = self.relationship.history
        self.relationship_understanding = self.relationship.understanding
        self.relationship_milestones = self.relationship.milestones

        self.creator_directives = CreatorDirectiveSystem()
        self.creator_directives.load()

        # ============================================================
        # LLM
        # ============================================================

        self.llm = self._create_llm_router()

        # ============================================================
        # TOOLS
        # ============================================================

        self.tools = ToolManager(
            workspace_root=self.config.paths.root,
        )

        self.code_change_planner = CodeChangePlanner(
            llm=self.llm,
            code=self.tools.code,
        )

        # ============================================================
        # CONVERSATION
        # ============================================================

        self.conversation = ConversationService(
            router=self.llm,
        )

        # ============================================================
        # EXPRESSION
        # ============================================================

        self.emotion = EmotionManager()

        self.response = ResponseBuilder()

        self.dialogue = DialogueManager()

        self.expression = ExpressionSystem(
            emotion=self.emotion,
            response=self.response,
            dialogue=self.dialogue,
        )

        # ============================================================
        # AVATAR
        # ============================================================

        self.avatar = AvatarBridge(
            emotion_manager=self.emotion,
        )

        # ============================================================
        # AUDIO
        # ============================================================

        self.audio = AudioManager(
            input_service=create_audio_input_service(
                NullAudioInputProvider(),
            ),
            output_service=create_audio_output_service(
                NullAudioOutputProvider(),
            ),
        )

        # ============================================================
        # LEARNING
        # ============================================================

        self.learner = Learner()

        self.evaluator = Evaluator(
            llm=self.llm,
        )

        self.source_resolver = SourceResolver()

        self.research_grounder = ResearchGrounder()

        self.claim_grounder = ClaimGrounder()

        self.evidence_validator = EvidenceValidator(
            claim_grounder=self.claim_grounder,
        )

        # ============================================================
        # RESEARCHER
        # ============================================================

        # Web execution is intentionally NOT injected directly here.
        # Mary coordinates approved ToolRegistry results into Researcher so
        # Researcher cannot bypass the creator-approval boundary.
        self.researcher = Researcher(
            web_tool=None,
        )

        # ============================================================
        # KNOWLEDGE
        # ============================================================

        self.knowledge = KnowledgeManager()

        # ============================================================
        # MEMORY
        # ============================================================

        self.memory = MemoryManager()

        # Build structured creator understanding from older explicit memories
        # using only the relationship manager's narrow high-confidence parser.
        self._sync_relationship_from_existing_memories()

        # ============================================================
        # COGNITION
        # ============================================================

        self.reasoning = ReasoningEngine(
            llm=self.llm,
            evidence_validator=self.evidence_validator,
        )

        self.reflection = ReflectionEngine(
            llm=self.llm,
        )

        self.cognition = CognitiveOrchestrator(
            reasoning_engine=self.reasoning,
            reflection_engine=self.reflection,
        )

        # ============================================================
        # AGENCY
        # ============================================================

        self.agency = Agency()
        self.agency.load()

        self.relationship_curiosity = RelationshipCuriosityDevelopment(
            relationship=self.relationship,
            curiosity_system=self.agency.curiosities,
            creator_name=str(self.user_model.name or self.identity.creator or "Unbe").title(),
        )
        self.relationship_curiosity.sync()
        self.agency.rebuild_priorities()

        # ============================================================
        # AUTONOMY
        # ============================================================

        self.autonomy = AutonomyRuntime()

        # ============================================================
        # SELF INTROSPECTION
        # ============================================================

        self.self_introspection = SelfIntrospection(
            identity=self.identity,
            self_model=self.self_model,
            biography=self.biography,
            personality=self.personality,
            values=self.values,
            character=self.character,
            user_model=self.user_model,
            creator_directives=self.creator_directives,
            agency=self.agency,
            autonomy=self.autonomy,
            tools=self.tools,
        )

    # ================================================================
    # PRIMARY ENTRY POINT
    # ================================================================

    def process(
        self,
        input_text: str,
    ) -> CognitiveCycleResult:
        """
        Process one complete MaryV2 interaction.
        """

        input_text = self._normalize_input(
            input_text
        )

        context = self._build_context(
            input_text
        )

        intent = self._detect_intent(
            input_text
        )

        system_response: str | None = None
        external_knowledge: list[Any] = []
        external_sources: list[dict[str, Any]] = []
        skip_cognition = False

        if intent.intent_type == IntentType.RELATIONSHIP_SHARE:
            relationship_action = self._handle_relationship_share(intent)
            system_response = relationship_action.get("system_response")
            skip_cognition = True

        elif intent.intent_type == IntentType.RELATIONSHIP_QUERY:
            relationship_action = self._handle_relationship_query(intent)
            system_response = relationship_action.get("system_response")
            skip_cognition = True

        elif intent.intent_type == IntentType.CREATOR_DIRECTIVE:
            directive_action = self._handle_creator_directive(
                intent
            )
            system_response = directive_action.get(
                "system_response"
            )
            skip_cognition = True

        elif intent.intent_type == IntentType.SELF_QUERY:
            self_action = self._handle_self_query(
                intent
            )
            external_knowledge = list(
                self_action.get(
                    "knowledge",
                    [],
                )
            )

        elif intent.intent_type == IntentType.WEB_SEARCH:
            web_action = self._handle_web_intent(
                intent,
                original_input=input_text,
            )
            system_response = web_action.get(
                "system_response"
            )
            external_knowledge = list(
                web_action.get(
                    "knowledge",
                    [],
                )
            )
            external_sources = list(
                web_action.get(
                    "sources",
                    [],
                )
            )

        elif intent.intent_type == IntentType.TOOL_USE:
            action = str(
                intent.parameters.get(
                    "action",
                    "",
                )
            ).strip().lower()

            if action in {"approve", "reject"}:
                tool_action = self._handle_tool_control(
                    intent
                )
            elif action == "propose_code_change":
                tool_action = self._handle_code_change_proposal(
                    intent,
                    original_input=input_text,
                )
            else:
                tool_action = self._handle_local_tool_intent(
                    intent,
                    original_input=input_text,
                )

            system_response = tool_action.get(
                "system_response"
            )
            external_knowledge = list(
                tool_action.get(
                    "knowledge",
                    [],
                )
            )
            external_sources = list(
                tool_action.get(
                    "sources",
                    [],
                )
            )
            skip_cognition = bool(
                tool_action.get(
                    "skip_cognition",
                    False,
                )
            )

        else:
            system_response = self._handle_intent(
                intent
            )

        # Deterministic tool/system responses must not fall through into an
        # unnecessary LLM call.  This includes pending approval prompts, tool
        # failures, approvals/rejections, and validated code proposals.  A web
        # action that returned grounded knowledge still goes through cognition
        # because the LLM is needed to synthesize the sourced answer.
        if (
            system_response is not None
            and not external_knowledge
            and intent.intent_type in {
                IntentType.WEB_SEARCH,
                IntentType.TOOL_USE,
                IntentType.MEMORY_STORE,
                IntentType.MEMORY_RECALL,
                IntentType.CREATOR_DIRECTIVE,
                IntentType.RELATIONSHIP_SHARE,
                IntentType.RELATIONSHIP_QUERY,
            }
        ):
            skip_cognition = True

        if system_response is not None:
            context["memory"] = self.memory.build_context(
                input_text
            )

        if skip_cognition and system_response is not None:
            system_action = str(
                intent.parameters.get(
                    "action",
                    intent.intent_type.value,
                )
            ).strip() or intent.intent_type.value

            metadata = {
                "handled_by": "mary_system",
                "system_action": system_action,
                "llm_calls_after_action": 0,
            }
            if system_action == "propose_code_change":
                metadata.update({
                    "handled_by": "mary_code_change_planner",
                    "llm_calls_after_planning": 0,
                })

            return self._build_system_cycle_result(
                input_text=input_text,
                intent=intent,
                response=system_response,
                context=context,
                metadata=metadata,
            )

        result = self.cognition.process(
            input_text=input_text,
            intent=intent,
            memories=context["memory"].get(
                "relevant_memories",
                [],
            ),
            knowledge=external_knowledge,
            user_context=context["user"],
            personality_context=context["personality"],
        )

        if system_response is not None:
            result.final_response = system_response
            result.metadata.update(
                {
                    "handled_by": "mary",
                    "system_action": (
                        intent.intent_type.value
                        if intent is not None
                        else None
                    ),
                }
            )

        elif external_sources:
            result.final_response = (
                result.final_response.rstrip()
                + self._format_source_footer(
                    external_sources
                )
            )
            result.metadata.update(
                {
                    "handled_by": "mary_research",
                    "web_sources": external_sources,
                }
            )

        return result

    # ================================================================
    # INPUT
    # ================================================================

    def _normalize_input(
        self,
        input_text: str,
    ) -> str:
        """
        Validate and normalize input.
        """

        if input_text is None:

            raise ValueError(
                "input_text cannot be None."
            )

        text = str(
            input_text
        ).strip()

        if not text:

            raise ValueError(
                "input_text cannot be empty."
            )

        return text

    # ================================================================
    # CONTEXT
    # ================================================================

    def _build_context(
        self,
        input_text: str,
    ) -> dict[str, Any]:
        """
        Build the subsystem context required for one cognitive cycle.
        """

        return {
            "memory": self.memory.build_context(
                input_text
            ),
            "user": self._user_context(),
            "personality": self._personality_context(),
        }

    # ================================================================
    # INTENT
    # ================================================================

    def _detect_intent(
        self,
        input_text: str,
    ) -> Intent:
        """
        Ask cognition to classify the user's intent.
        """

        return self.cognition.detect_intent(
            input_text
        )

    def _handle_intent(
        self,
        intent: Intent | None,
    ) -> str | None:
        """
        Execute deterministic subsystem actions.
        """

        if intent is None:
            return None

        if intent.intent_type == IntentType.MEMORY_STORE:

            return self._handle_memory_store(
                intent
            )

        if intent.intent_type == IntentType.MEMORY_RECALL:

            return self._handle_memory_recall(
                intent
            )

        return None

    # ================================================================
    # RELATIONSHIP DEVELOPMENT
    # ================================================================

    def _handle_relationship_share(
        self,
        intent: Intent,
    ) -> dict[str, Any]:
        """Store an explicit creator share in memory and structured relationship state."""

        content = str(intent.parameters.get("content", "")).strip()
        if not content:
            return {"system_response": "What would you like me to learn about you?"}

        memory = self.remember(
            content,
            memory_type="episodic",
            importance=0.8,
            metadata={
                "source": "interaction",
                "event_type": "creator_relationship_share",
                "owner": "creator",
                "speaker": "Unbe",
                "perspective": "creator_first_person",
            },
        )
        if memory is None:
            return {"system_response": "I wasn't able to preserve that relationship share."}

        learned = self.relationship.learn_explicit(
            content,
            source="creator_explicit",
            evidence_id=str(getattr(memory, "id", "") or "") or None,
            force_general=bool(intent.parameters.get("force_general", True)),
        )
        if learned is None:
            return {
                "system_response": (
                    "I preserved that in memory, but I didn't promote it into my "
                    "structured creator model because it wasn't specific enough."
                )
            }

        self._advance_creator_curiosity(learned)
        return {
            "system_response": (
                "Got it. I've preserved that in memory and added it to my "
                f"structured understanding of Unbe as {learned.get('label', learned.get('category', 'information'))}."
            )
        }

    def _handle_relationship_query(
        self,
        intent: Intent,
    ) -> dict[str, Any]:
        """Answer from Mary's local structured creator model without web or LLM."""

        query_type = str(
            intent.parameters.get("relationship_query_type", "overview")
        ).strip().lower()
        if query_type == "curiosity_gaps":
            self.relationship_curiosity.sync()
            self.agency.rebuild_priorities()
            response = self.relationship_curiosity.answer_query()
        else:
            response = self.relationship.answer_query(query_type)

        return {
            "system_response": response
        }

    def _advance_creator_curiosity(
        self,
        learned: dict[str, Any],
    ) -> None:
        """Record progress on the persistent Learn-more-about-Unbe curiosity."""

        changed = False
        for curiosity in self.agency.curiosities.get_curiosities():
            if curiosity.get("status") not in {"open", "exploring"}:
                continue
            if str(curiosity.get("description", "")).strip().lower() != "learn more about unbe":
                continue

            curiosity["status"] = "exploring"
            curiosity["progress_count"] = int(curiosity.get("progress_count", 0)) + 1
            curiosity["last_learned_category"] = learned.get("category")
            curiosity["last_learned_value"] = learned.get("value")
            changed = True

        if changed:
            self.agency.curiosities.save()

        relationship_curiosity = getattr(self, "relationship_curiosity", None)
        if relationship_curiosity is not None:
            relationship_curiosity.sync()

        if hasattr(self, "agency"):
            self.agency.rebuild_priorities()

    def _sync_relationship_from_existing_memories(self) -> None:
        """Safely import high-confidence explicit creator statements from older memory."""

        episodic = getattr(self.memory, "episodic", None)
        all_memories = getattr(episodic, "all", None)
        if not callable(all_memories):
            return

        changed = False
        for memory in all_memories():
            content = str(getattr(memory, "content", "") or "").strip()
            if not content:
                continue
            memory_id = str(getattr(memory, "id", "") or "") or None
            learned = self.relationship.learn_explicit(
                content,
                source="explicit_memory_import",
                evidence_id=memory_id,
                force_general=False,
            )
            if learned is not None and not learned.get("already_known"):
                changed = True

        if changed:
            self.relationship.save()

    # ================================================================
    # CREATOR DIRECTIVES
    # ================================================================

    def _handle_creator_directive(
        self,
        intent: Intent,
    ) -> dict[str, Any]:
        """Apply an explicit creator direction to Mary's internal state."""

        directive_type = str(
            intent.parameters.get("directive_type", "")
        ).strip().lower()

        if directive_type != "creator_curiosity":
            return {
                "system_response": (
                    "I recognized that as a creator directive, but this directive "
                    "type is not connected yet."
                )
            }

        creator_name = str(
            self.user_model.name or self.identity.creator or "Unbe"
        ).strip() or "Unbe"
        target = str(
            intent.parameters.get("target", "unbe")
        ).strip().lower() or "unbe"
        instruction = str(
            intent.parameters.get("instruction", "")
        ).strip()
        priority = float(
            intent.parameters.get("priority", 0.9)
        )
        top_priority = bool(
            intent.parameters.get("top_priority", False)
        )

        directive = self.creator_directives.add(
            instruction=instruction,
            category="relationship_curiosity",
            target=target,
            priority=priority,
            metadata={
                "creator_name": creator_name,
                "top_priority": top_priority,
            },
        )

        if directive is None:
            return {
                "system_response": "I wasn't able to store that creator directive."
            }

        description = f"Learn more about {creator_name.title()}"
        existing = None
        for curiosity in self.agency.curiosities.get_curiosities():
            if str(curiosity.get("description", "")).strip().lower() != description.lower():
                continue
            if curiosity.get("status") not in {"open", "exploring"}:
                continue
            existing = curiosity
            break

        if existing is None:
            curiosity = self.agency.curiosities.add_curiosity(
                description=description,
                importance=1.0 if top_priority else priority,
                source="creator_directive",
            )
        else:
            curiosity = existing
            self.agency.curiosities.update_curiosity(
                str(curiosity.get("id", "")),
                importance=1.0 if top_priority else priority,
                source="creator_directive",
            )

        if curiosity is not None:
            curiosity["urgency"] = 1.0 if top_priority else 0.5
            curiosity["relevance"] = 1.0
            curiosity["directive_id"] = directive.get("id")
            curiosity["creator_directed"] = True
            self.agency.curiosities.save()

        self.relationship_curiosity.sync()
        self.agency.rebuild_priorities()

        if top_priority:
            response = (
                f"Understood. I've made learning more about {creator_name.title()} "
                "an active creator-directed curiosity and top internal priority."
            )
        else:
            response = (
                f"Understood. I've made learning more about {creator_name.title()} "
                "an active creator-directed curiosity."
            )

        return {
            "system_response": response,
        }

    # ================================================================
    # SELF INTROSPECTION
    # ================================================================

    def _handle_self_query(
        self,
        intent: Intent,
    ) -> dict[str, Any]:
        """Provide grounded local evidence for questions about Mary herself."""

        subtype = str(
            intent.parameters.get(
                "self_query_type",
                "identity",
            )
        ).strip().lower()

        evidence = self.self_introspection.build(
            subtype
        )

        return {
            "knowledge": [evidence],
        }

    # ================================================================
    # TOOLS / WEB RESEARCH
    # ================================================================

    def _handle_web_intent(
        self,
        intent: Intent,
        *,
        original_input: str,
    ) -> dict[str, Any]:
        """Handle a purposeful web search or web-page retrieval request."""

        operation = str(
            intent.parameters.get(
                "operation",
                "search",
            )
        ).strip().lower()

        explicit = bool(
            intent.parameters.get(
                "explicit_creator_request",
                False,
            )
        )

        if operation == "fetch":
            tool_name = "web_fetch"
            url = str(
                intent.parameters.get(
                    "url",
                    "",
                )
            ).strip()
            arguments = {
                "url": url,
            }
            query = str(
                intent.parameters.get(
                    "query",
                    url,
                )
            ).strip()
        else:
            tool_name = "web_search"
            query = str(
                intent.parameters.get(
                    "query",
                    original_input,
                )
            ).strip()
            arguments = {
                "query": query,
                # Retrieve a broader candidate set in one approved search
                # call, then resolve/rank locally down to the strongest five.
                "limit": 10,
            }

        reason = (
            "Creator requested external information for: "
            f"{original_input}"
        )

        if not explicit:
            request = self.tools.request(
                tool_name,
                arguments,
                reason=reason,
            )

            if request.status != "pending":
                return {
                    "system_response": (
                        "I couldn't create the required tool request."
                    )
                }

            return {
                "system_response": (
                    "Current external information would help answer that. "
                    f"I created {request.request_id} for {tool_name}. "
                    "To authorize exactly that request, say: "
                    f"approve {request.request_id}. "
                    "If it is the only pending request, you can simply say: approve"
                )
            }

        request, tool_result = (
            self.tools.execute_explicit_creator_request(
                tool_name,
                arguments,
                reason=reason,
            )
        )

        return self._research_from_tool_result(
            tool_result,
            query=query,
            tool_name=tool_name,
            request_id=request.request_id,
        )

    def _handle_code_change_proposal(
        self,
        intent: Intent,
        *,
        original_input: str,
    ) -> dict[str, Any]:
        """Plan, validate, and present a code change without applying it."""

        path = str(
            intent.parameters.get(
                "path",
                "",
            )
        ).strip()
        instruction = str(
            intent.parameters.get(
                "instruction",
                "",
            )
        ).strip()

        try:
            plan = self.code_change_planner.propose(
                path,
                instruction,
            )
        except Exception as exc:
            return {
                "system_response": (
                    "I couldn't create a safe grounded code proposal: "
                    f"{exc}"
                ),
                "skip_cognition": True,
            }

        change = plan.change
        request = self.tools.request(
            "code_apply_change",
            {
                "change": change.to_dict(),
            },
            reason=(
                "Creator requested this exact proposed source change: "
                f"{original_input}"
            ),
        )

        if request.status != "pending":
            return {
                "system_response": (
                    "The proposal was generated and validated, but I couldn't "
                    "create the approval request needed to apply it."
                ),
                "skip_cognition": True,
            }

        diff_text = change.diff.strip() or "(no textual diff)"
        if len(diff_text) > 14_000:
            diff_text = (
                diff_text[:14_000].rstrip()
                + "\n...[diff truncated for display]"
            )

        validation = plan.validation
        warning_text = ""
        warnings = validation.get("warnings") or []
        if warnings:
            warning_text = (
                "\nStatic warnings: "
                + "; ".join(str(item) for item in warnings)
            )

        response = (
            f"Proposed change for `{change.path}`\n\n"
            f"Summary: {plan.summary}\n"
            f"Static syntax validation: PASS"
            f"{warning_text}\n\n"
            "Nothing has been written or executed.\n\n"
            "```diff\n"
            f"{diff_text}\n"
            "```\n\n"
            f"Approval request: {request.request_id}\n"
            "To apply exactly this validated proposal, say: "
            f"approve {request.request_id}.\n"
            "If it is the only pending request, you can simply say: approve"
        )

        return {
            "system_response": response,
            "skip_cognition": True,
            "proposal": plan.to_dict(),
        }

    def _build_system_cycle_result(
        self,
        *,
        input_text: str,
        intent: Intent | None,
        response: str,
        context: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveCycleResult:
        """Return a deterministic system result without another LLM call."""

        cognitive_context = CognitiveContext(
            input_text=input_text,
            memories=list(
                context.get("memory", {}).get(
                    "relevant_memories",
                    [],
                )
            ),
            user_context=dict(
                context.get("user", {})
            ),
            personality_context=dict(
                context.get("personality", {})
            ),
        )

        reasoning = ReasoningResult(
            response=response,
            confidence=1.0,
            reasoning_type="deterministic_system_action",
            intent=intent,
            metadata={
                "llm_skipped": True,
            },
        )
        reflection = ReflectionResult(
            decision=ReflectionDecision.ACCEPT,
            confidence=1.0,
            assessment=(
                "Deterministic system action; no second LLM pass required."
            ),
            metadata={
                "mode": "deterministic_system_action",
            },
        )

        return CognitiveCycleResult(
            context=cognitive_context,
            intent=intent,
            reasoning=reasoning,
            reflection=reflection,
            final_response=response,
            metadata=dict(metadata or {}),
        )

    def _handle_local_tool_intent(
        self,
        intent: Intent,
        *,
        original_input: str,
    ) -> dict[str, Any]:
        """
        Execute an intentional local SAFE tool or request approval for a
        state-changing local tool.

        SAFE here means the ToolRegistry definition is read-only/non-external.
        Mutating and creator-sensitive tools always require a separate approval
        turn even when the creator explicitly asked for the mutation initially.
        """

        tool_name = str(
            intent.parameters.get(
                "tool_name",
                "",
            )
        ).strip()
        arguments = dict(
            intent.parameters.get(
                "arguments",
                {},
            )
            or {}
        )

        if not tool_name:
            return {
                "system_response": "I couldn't determine which local tool to use."
            }

        definition = self.tools.registry.get(
            tool_name
        )
        if definition is None or not definition.enabled:
            return {
                "system_response": f"The local tool {tool_name} is unavailable."
            }

        valid, validation_error = self.tools.registry.validate(
            tool_name,
            arguments,
        )
        if not valid:
            return {
                "system_response": (
                    f"I couldn't prepare {tool_name}: "
                    f"{validation_error or 'invalid arguments'}"
                )
            }

        if definition.permission_level == PermissionLevel.SAFE:
            tool_result = self.tools.registry.execute_validated(
                tool_name,
                arguments,
            )
            return self._local_tool_result_to_context(
                tool_result,
                original_input=original_input,
            )

        if definition.permission_level == PermissionLevel.NEVER_AUTONOMOUS:
            return {
                "system_response": (
                    f"{tool_name} cannot run through Mary's normal tool path."
                )
            }

        request = self.tools.request(
            tool_name,
            arguments,
            reason=(
                "Creator requested a state-changing local operation: "
                f"{original_input}"
            ),
        )

        if request.status != "pending":
            return {
                "system_response": (
                    f"I couldn't create an approval request for {tool_name}."
                )
            }

        return {
            "system_response": (
                f"{tool_name} would change Mary's workspace. "
                f"I created {request.request_id}. "
                "To authorize exactly that operation, say: "
                f"approve {request.request_id}. "
                "If it is the only pending request, you can simply say: approve"
            )
        }

    def _local_tool_result_to_context(
        self,
        tool_result: Any,
        *,
        original_input: str,
    ) -> dict[str, Any]:
        """Convert a read-only local tool result into bounded LLM context."""

        if not getattr(tool_result, "success", False):
            return {
                "system_response": (
                    f"{getattr(tool_result, 'tool_name', 'local tool')} failed: "
                    f"{getattr(tool_result, 'error', None) or 'unknown error'}"
                )
            }

        raw_result = getattr(tool_result, "result", None)

        def serializable(value: Any) -> Any:
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            if isinstance(value, dict):
                return {
                    str(key): serializable(item)
                    for key, item in value.items()
                }
            if isinstance(value, (list, tuple)):
                return [
                    serializable(item)
                    for item in value[:75]
                ]
            to_dict = getattr(value, "to_dict", None)
            if callable(to_dict):
                return serializable(to_dict())
            return str(value)

        normalized = serializable(raw_result)
        rendered = json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        tool_name = getattr(
            tool_result,
            "tool_name",
            "local_tool",
        )

        # Code reads/analysis need enough exact source evidence for grounded
        # explanation. Other local tool results stay smaller to protect the
        # LLM context/token budget.
        max_chars = (
            13_000
            if tool_name in {"code_analyze", "code_read"}
            else 6_000
        )
        truncated = len(rendered) > max_chars
        if truncated:
            rendered = rendered[:max_chars].rstrip() + "\n...[tool result truncated]"

        return {
            "knowledge": [
                {
                    "local_tool": True,
                    "tool_name": tool_name,
                    "request": original_input,
                    "content": rendered,
                    "truncated": truncated,
                }
            ]
        }

    def _handle_tool_control(
        self,
        intent: Intent,
    ) -> dict[str, Any]:
        """Handle creator approval/rejection of a pending tool request.

        A request id is always accepted.  Bare ``approve`` or ``reject`` is a
        convenience for the creator only when exactly one request is pending.
        Mary never guesses which request to authorize when more than one exists.
        """

        action = str(
            intent.parameters.get(
                "action",
                "",
            )
        ).strip().lower()

        request_id = str(
            intent.parameters.get(
                "request_id",
                "",
            )
        ).strip()

        if not request_id:
            pending = self.tools.pending_requests()

            if not pending:
                return {
                    "system_response": (
                        "There are no pending tool requests to "
                        f"{action or 'control'}."
                    ),
                    "skip_cognition": True,
                }

            if len(pending) > 1:
                choices = "\n".join(
                    f"- {item.request_id}: {item.tool_name}"
                    for item in pending
                )
                return {
                    "system_response": (
                        "More than one tool request is pending, so I won't "
                        "guess which one you mean. Use the full request id:\n"
                        f"{choices}"
                    ),
                    "skip_cognition": True,
                }

            request_id = pending[0].request_id

        request = self.tools.registry.get_request(
            request_id
        )

        if request is None or request.status != "pending":
            return {
                "system_response": (
                    f"I don't have a pending tool request named {request_id}."
                ),
                "skip_cognition": True,
            }

        if action == "reject":
            rejected = self.tools.reject(
                request_id
            )
            return {
                "system_response": (
                    f"Rejected {request_id}."
                    if rejected
                    else f"{request_id} could not be rejected."
                ),
                "skip_cognition": True,
            }

        if action != "approve":
            return {
                "system_response": (
                    "I don't recognize that tool-control action."
                ),
                "skip_cognition": True,
            }

        token = self.tools.approve(
            request_id,
            reason="Explicit creator approval in conversation.",
        )

        if token is None:
            return {
                "system_response": (
                    f"{request_id} could not be approved."
                ),
                "skip_cognition": True,
            }

        tool_result = self.tools.execute_approved(
            request_id
        )

        if request.tool_name in {
            "web_search",
            "web_fetch",
        }:
            query = str(
                request.arguments.get(
                    "query",
                    request.arguments.get(
                        "url",
                        "",
                    ),
                )
            ).strip()

            return self._research_from_tool_result(
                tool_result,
                query=query,
                tool_name=request.tool_name,
                request_id=request_id,
            )

        if not tool_result.success:
            return {
                "system_response": (
                    f"{request.tool_name} failed: "
                    f"{tool_result.error or 'unknown error'}"
                ),
                "skip_cognition": True,
            }

        if request.tool_name == "code_apply_change":
            return {
                "system_response": (
                    "Applied the exact approved code proposal to "
                    f"{tool_result.result}. No code or tests were executed."
                ),
                "skip_cognition": True,
            }

        return {
            "system_response": (
                f"{request.tool_name} completed: "
                f"{tool_result.result}"
            ),
            "skip_cognition": True,
        }

    def _research_from_tool_result(
        self,
        tool_result: Any,
        *,
        query: str,
        tool_name: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Route approved web output through Researcher and Evaluator."""

        if not getattr(
            tool_result,
            "success",
            False,
        ):
            return {
                "system_response": (
                    f"{tool_name} failed: "
                    f"{getattr(tool_result, 'error', None) or 'unknown error'}"
                )
            }

        raw_result = getattr(
            tool_result,
            "result",
            None,
        )

        if raw_result is None:
            raw_sources: Any = []
        elif isinstance(raw_result, (list, tuple, dict)):
            raw_sources = raw_result
        else:
            to_dict = getattr(
                raw_result,
                "to_dict",
                None,
            )
            raw_sources = [
                to_dict()
                if callable(to_dict)
                else raw_result
            ]

        research_request = self.researcher.create_request(
            query,
            purpose=(
                "Answer the creator's current request using "
                "approved external information."
            ),
            source_limit=10,
            metadata={
                "tool_request_id": request_id,
                "tool_name": tool_name,
            },
        )

        research_result = self.researcher.complete_with_sources(
            research_request,
            raw_sources,
        )

        if not research_result.sources:
            return {
                "system_response": (
                    "The web request completed, but it returned no usable sources."
                )
            }

        knowledge: list[dict[str, Any]] = []
        source_cards: list[dict[str, Any]] = []

        resolved_sources = self.source_resolver.resolve(
            query,
            research_result.sources,
            max_sources=10,
        )

        grounded_sources = self.research_grounder.rank_sources(
            query,
            resolved_sources,
        )[:5]

        for source, grounding in grounded_sources:
            statement = (
                source.content.strip()
                or source.title.strip()
            )

            evaluation = self.evaluator.evaluate(
                subject=query,
                statement=statement,
                source=source,
                context=query,
                metadata={
                    "url": source.url,
                    "research_request_id": research_request.id,
                    "grounding": grounding.to_dict(),
                },
            )

            knowledge.append(
                {
                    "title": source.title,
                    "url": source.url,
                    "content": statement[:4000],
                    "source_type": source.source_type,
                    "research_grounding": grounding.to_dict(),
                    "source_resolution": dict(
                        source.metadata.get("source_resolution", {})
                    ),
                    "evaluation": {
                        "recommendation": evaluation.recommendation,
                        "confidence": evaluation.confidence,
                        "reliability": evaluation.reliability,
                    },
                }
            )

            source_cards.append(
                {
                    "title": source.title,
                    "url": source.url,
                    "confidence": evaluation.confidence,
                    "recommendation": evaluation.recommendation,
                    "grounding": grounding.to_dict(),
                    "resolution": dict(
                        source.metadata.get("source_resolution", {})
                    ),
                }
            )

        return {
            "knowledge": knowledge,
            "sources": source_cards,
        }

    @staticmethod
    def _format_source_footer(
        sources: list[dict[str, Any]],
    ) -> str:
        """Append compact source attribution to a researched response."""

        unique: list[tuple[str, str]] = []
        seen: set[str] = set()

        for source in sources:
            url = str(
                source.get("url", "")
            ).strip()
            title = str(
                source.get("title", "Source")
            ).strip() or "Source"

            key = url or title
            if not key or key in seen:
                continue

            seen.add(key)
            unique.append((title, url))

        if not unique:
            return ""

        lines = ["", "", "Sources:"]
        for title, url in unique[:5]:
            lines.append(
                f"- {title}: {url}"
                if url
                else f"- {title}"
            )

        return "\n".join(lines)

    # ================================================================
    # MEMORY STORE
    # ================================================================

    def _handle_memory_store(
        self,
        intent: Intent,
    ) -> str:
        """
        Handle an explicit request to store information.
        """

        content = intent.parameters.get(
            "content"
        )

        if content is None:

            return (
                "What would you like me to remember?"
            )

        content = str(
            content
        ).strip()

        if not content:

            return (
                "What would you like me to remember?"
            )

        memory = self.remember(
            content,
            memory_type="episodic",
            importance=0.8,
            metadata={
                "source": "interaction",
                "event_type": "user_statement",
                "owner": "creator",
                "speaker": "Unbe",
                "perspective": "creator_first_person",
            },
        )

        if memory is None:

            return (
                "I wasn't able to store that memory."
            )

        learned = self.relationship.learn_explicit(
            content,
            source="explicit_memory",
            evidence_id=str(getattr(memory, "id", "") or "") or None,
            force_general=False,
        )
        if learned is not None and not learned.get("already_known"):
            self._advance_creator_curiosity(learned)

        rendered_content = (
            self._creator_to_second_person(
                content
            )
        )

        return (
            "Got it. I'll remember that "
            f"{rendered_content}."
        )

    # ================================================================
    # MEMORY RECALL
    # ================================================================

    def _handle_memory_recall(
        self,
        intent: Intent,
    ) -> str:
        """
        Handle an explicit request to recall information.
        """

        query = intent.parameters.get(
            "query",
            "",
        )

        query = str(
            query
        ).strip()

        if self._is_broad_memory_query(
            query
        ):

            memories = self._all_available_memories()

            if not memories:

                return (
                    "I don't have any stored memories "
                    "about you yet."
                )

        else:

            memories = self.memory.recall(
                query,
                limit=5,
            )

            if not memories:

                return (
                    "I don't have a stored memory "
                    "that answers that."
                )

        return self._format_memory_response(
            memories
        )

    def _is_broad_memory_query(
        self,
        query: str,
    ) -> bool:
        """
        Return True only for genuinely broad creator-memory queries.

        Specific questions such as "what do you remember about creation"
        must continue through MemoryRetriever instead of dumping every stored
        memory merely because they contain the words "what do you remember".
        """

        normalized = self.memory.retrieval._normalize_query(
            query
        )

        phrases = {
            "what do you remember",
            "what do you remember about me",
            "what do you know about me",
            "tell me what you remember",
            "tell me what you remember about me",
            "tell me what you know about me",
            "what are my preferences",
        }

        return normalized in phrases

    def _all_available_memories(
        self,
    ) -> list[Any]:
        """
        Return Mary's available stored memories.
        """

        episodic = list(
            self.memory.episodic.all()
        )

        if episodic:
            return episodic

        semantic = list(
            self.memory.semantic.all()
        )

        return semantic

    # ================================================================
    # MEMORY RESPONSE
    # ================================================================

    def _format_memory_response(
        self,
        memories: list[Any],
    ) -> str:
        """
        Convert memory records into a deterministic,
        human-readable response.
        """

        if not memories:

            return (
                "I don't have any relevant memories stored."
            )

        statements: list[str] = []

        for memory in memories:

            statement = self._memory_to_text(
                memory
            )

            if statement:

                statements.append(
                    statement
                )

        if not statements:

            return (
                "I found stored memories, but I couldn't "
                "turn them into an answer."
            )

        statements = list(
            dict.fromkeys(
                statements
            )
        )

        if len(statements) == 1:

            return (
                f"I remember that {statements[0]}"
            )

        lines = "\n".join(
            f"- {statement}"
            for statement in statements
        )

        return (
            "Here's what I remember:\n"
            f"{lines}"
        )

    def _memory_to_text(
        self,
        memory: Any,
    ) -> str | None:
        """
        Extract human-readable text from a memory representation.

        Creator-owned episodic memories are rendered from Mary's
        speaking perspective. The raw stored content is not mutated.
        """

        if isinstance(
            memory,
            dict,
        ):

            content = memory.get(
                "content"
            )

            if content:

                text = str(
                    content
                ).strip()

                if self._memory_is_creator_owned(
                    memory
                ):
                    return self._creator_to_second_person(
                        text
                    )

                return text

            subject = memory.get(
                "subject"
            )

            predicate = memory.get(
                "predicate"
            )

            value = memory.get(
                "value"
            )

            if (
                subject is not None
                and predicate is not None
                and value is not None
            ):

                return (
                    f"{subject} "
                    f"{predicate} "
                    f"{value}"
                ).strip()

            return None

        content = getattr(
            memory,
            "content",
            None,
        )

        if content:

            text = str(
                content
            ).strip()

            if self._memory_is_creator_owned(
                memory
            ):
                return self._creator_to_second_person(
                    text
                )

            return text

        return None

    def _memory_is_creator_owned(
        self,
        memory: Any,
    ) -> bool:
        """
        Determine whether a memory statement belongs to Mary's creator.

        New memories carry explicit ownership metadata. The
        user_preference fallback preserves correct rendering for older
        V2 memories written before ownership metadata was introduced.
        """

        if isinstance(memory, dict):
            metadata = memory.get(
                "metadata",
                {},
            )
            event_type = memory.get(
                "event_type"
            )
        else:
            metadata = getattr(
                memory,
                "metadata",
                {},
            )
            event_type = getattr(
                memory,
                "event_type",
                None,
            )

        if not isinstance(metadata, dict):
            metadata = {}

        owner = str(
            metadata.get(
                "owner",
                "",
            )
        ).strip().lower()

        if owner in {
            "creator",
            "user",
            "unbe",
        }:
            return True

        if owner in {
            "mary",
            "self",
        }:
            return False

        legacy_event_type = str(
            metadata.get(
                "event_type",
                event_type or "",
            )
        ).strip().lower()

        return legacy_event_type == "user_preference"

    @classmethod
    def _creator_to_second_person(
        cls,
        text: str,
    ) -> str:
        """
        Render creator-authored first-person text for Mary speaking back
        to the creator.

        Only text outside double/curly-double quoted spans is shifted,
        preserving quoted first-person speech. The stored memory itself
        remains unchanged.
        """

        text = str(text).strip()

        if not text:
            return text

        parts = re.split(
            r'("[^"\n]*"|“[^”\n]*”)',
            text,
        )

        rendered: list[str] = []

        for index, part in enumerate(parts):
            if index % 2 == 1:
                rendered.append(part)
                continue

            rendered.append(
                cls._shift_first_person_segment(
                    part
                )
            )

        return "".join(rendered)

    @classmethod
    def _shift_first_person_segment(
        cls,
        text: str,
    ) -> str:
        """Shift creator first-person pronouns to second person."""

        replacements = (
            (r"\bI\s+am\b", "you are"),
            (r"\bI\s+was\b", "you were"),
            (r"\bI'm\b", "you're"),
            (r"\bI've\b", "you've"),
            (r"\bI'll\b", "you'll"),
            (r"\bI'd\b", "you'd"),
            (r"\bmyself\b", "yourself"),
            (r"\bmine\b", "yours"),
            (r"\bmy\b", "your"),
            (r"\bme\b", "you"),
            (r"\bI\b", "you"),
        )

        result = text

        for pattern, replacement in replacements:
            result = re.sub(
                pattern,
                lambda match, value=replacement: (
                    cls._match_case(
                        match.group(0),
                        value,
                    )
                ),
                result,
                flags=re.IGNORECASE,
            )

        return result

    @staticmethod
    def _match_case(
        source: str,
        replacement: str,
    ) -> str:
        """Apply simple source capitalization to replacement text."""

        if source.isupper() and len(source) > 1:
            return replacement.upper()

        if source[:1].isupper():
            return (
                replacement[:1].upper()
                + replacement[1:]
            )

        return replacement

    # ================================================================
    # STATUS
    # ================================================================

    def status(
        self,
    ) -> dict[str, Any]:
        """
        Return Mary's current high-level system status.
        """

        return {
            "name": self.personality.name,
            "identity": self._identity_context(),
            "personality": (
                self._personality_context()
            ),
            "personality_development": (
                self.personality_development.summary()
            ),
            "user": self._user_context(),
            "learning": self.learner.summarize(),
            "memory": self.memory.status(),
            "tools": self.tools.status(),
            "cognition": {
                "reasoning": True,
                "reflection": True,
                "llm": self.llm.provider_name(),
                "model": self.llm.model_name(),
            },
        }

    # ================================================================
    # SELF DESCRIPTION
    # ================================================================

    def describe_self(
        self,
    ) -> str:
        """
        Return Mary's human-readable self description.
        """

        return self.personality.describe()

    # ================================================================
    # IDENTITY
    # ================================================================

    def _identity_context(
        self,
    ) -> dict[str, Any]:
        """
        Safely expose Mary's identity as structured context.
        """

        to_dict = getattr(
            self.identity,
            "to_dict",
            None,
        )

        if callable(
            to_dict
        ):

            result = to_dict()

            if isinstance(
                result,
                dict,
            ):
                return result

        describe = getattr(
            self.identity,
            "describe",
            None,
        )

        if callable(
            describe
        ):

            return {
                "description": describe()
            }

        return {
            "type": type(
                self.identity
            ).__name__
        }

    # ================================================================
    # USER
    # ================================================================

    def describe_user(
        self,
    ) -> dict[str, Any]:
        """
        Return Mary's structured understanding of her creator.
        """

        return self._user_context()

    def _user_context(
        self,
    ) -> dict[str, Any]:
        """
        Safely expose the current user-model context.
        """

        to_dict = getattr(
            self.user_model,
            "to_dict",
            None,
        )

        if callable(
            to_dict
        ):

            result = to_dict()

            if isinstance(
                result,
                dict,
            ):
                return result

        get_identity = getattr(
            self.user_model,
            "get_identity",
            None,
        )

        if callable(
            get_identity
        ):

            result = get_identity()

            if isinstance(
                result,
                dict,
            ):
                return result

        return {}

    # ================================================================
    # PERSONALITY
    # ================================================================

    def _personality_context(
        self,
    ) -> dict[str, Any]:
        """
        Safely expose Mary's personality state.
        """

        get_traits = getattr(
            self.personality,
            "get_traits",
            None,
        )

        if not callable(
            get_traits
        ):

            return {}

        result = get_traits()

        if isinstance(
            result,
            dict,
        ):

            return result

        return {}

    def personality_development_summary(
        self,
    ) -> dict[str, Any]:
        """
        Return Mary's current personality-development state.
        """

        return self.personality_development.summary()

    def propose_personality_change(
        self,
        trait: str,
        amount: float,
        reason: str,
        *,
        confidence: float = 0.5,
        source: str = "experience",
    ):
        """
        Propose a controlled personality change.
        """

        return self.personality_development.propose_change(
            trait=trait,
            change=amount,
            reason=reason,
            confidence=confidence,
            source=source,
        )

    def apply_personality_change(
        self,
        proposal: dict[str, Any],
    ) -> bool:
        """
        Apply an approved personality-development proposal.
        """

        return self.personality_development.apply(
            proposal,
        )

    def reject_personality_change(
        self,
        proposal: dict[str, Any],
        reason: str = "",
    ) -> bool:
        """
        Reject a personality-development proposal.
        """

        return self.personality_development.reject(
            proposal,
            reason=reason,
        )

    # ================================================================
    # LEARNING
    # ================================================================

    def learn(
        self,
        event_type: str,
        subject: str,
        content: str,
        *,
        source: str | None = None,
        confidence: float = 0.5,
        usefulness: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Record something Mary may learn from.
        """

        return self.learner.record(
            event_type=event_type,
            subject=subject,
            content=content,
            source=source,
            confidence=confidence,
            usefulness=usefulness,
            metadata=metadata,
        )

    # ================================================================
    # MEMORY
    # ================================================================

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Store a memory through Mary's MemoryManager.
        """

        return self.memory.remember(
            content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )

    # ================================================================
    # INTERNAL
    # ================================================================

    def _create_llm_router(
        self,
    ):
        """
        Create Mary's LLM router.
        """

        from mary.llm.router import LLMRouter

        return LLMRouter(
            config=self.config,
        )