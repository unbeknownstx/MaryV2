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
from mary.conversation.engagement import ConversationEngagement

from mary.expression.dialogue import DialogueManager
from mary.expression.emotion import EmotionManager
from mary.expression.appraisal import ConversationEmotionAppraiser
from mary.expression.response import ResponseBuilder
from mary.expression.expression import ExpressionSystem
from mary.expression.director import ExpressionDirector

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
from mary.identity.self_provenance import SelfProvenance

from mary.personality.personality import Personality
from mary.personality.development import PersonalityDevelopment
from mary.personality.character import Character
from mary.personality.values import Values
from mary.personality.preferences import Preferences
from mary.personality.developed_state import DevelopedSelfStateStore
from mary.personality.preference_promotion import PreferencePromotionSystem

from mary.relationship.manager import RelationshipManager
from mary.relationship.directives import CreatorDirectiveSystem
from mary.relationship.curiosity_development import RelationshipCuriosityDevelopment
from mary.relationship.conversation_learning import ConversationLearningBridge
from mary.relationship.natural_learning import NaturalRelationshipLearner
from mary.relationship.provenance import conversation_profile, text_has_test_probe_marker

from mary.learning.learner import Learner
from mary.learning.evaluator import Evaluator
from mary.learning.knowledge import LearningKnowledge
from mary.learning.knowledge_bridge import KnowledgeLearningBridge
from mary.learning.knowledge_state import KnowledgeStateStore
from mary.learning.researcher import Researcher
from mary.learning.grounding import ResearchGrounder
from mary.learning.source_resolver import SourceResolver
from mary.learning.evidence import ClaimGrounder, EvidenceValidator

from mary.tools.manager import ToolManager
from mary.tools.registry import PermissionLevel

from mary.knowledge.manager import KnowledgeManager

from mary.memory.manager import MemoryManager

from mary.orchestration.workspace import TaskWorkspaceManager
from mary.orchestration.consultation import ExpertConsultant
from mary.orchestration.orchestrator import TaskOrchestrator
from mary.orchestration.execution import OrchestrationExecutor

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
from mary.cognition.mind_state import TurnMindStateBuilder
from mary.cognition.context_lifecycle import ConversationContextLifecycle
from mary.cognition.intent import Intent, IntentType
from mary.cognition.natural_input import normalize_for_matching
from mary.runtime.turn_policy import TurnPolicyEngine
from mary.runtime.turn_envelope import attach_turn_envelope
from mary.runtime.system_contract import MarySystemContract
from mary.runtime.environment import RuntimeEnvironment
from mary.realtime import RealtimeInteractionCoordinator
from mary.distributed import NodeRegistry
from mary.perception import PerceptionDirector
from mary.runtime.introspection import RuntimeIntrospection, is_personal_runtime_reaction
from mary.mind import CharacterMind
from mary.mind.production_bridge import (
    apply_local_cycle_metadata,
    merge_escalated_cycle_metadata,
    safe_local_metadata,
)
from mary.development import GrowthEngine
from mary.training import ResponseFeedbackStore


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

        self.config = Config.from_environment()

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

        # ============================================================
        # CHARACTER
        # ============================================================

        self.character = Character()

        # ============================================================
        # VALUES
        # ============================================================

        self.values = Values()

        # ============================================================
        # PREFERENCES
        # ============================================================

        self.preferences = Preferences()

        # ============================================================
        # PERSONALITY DEVELOPMENT / DEVELOPED SELF STATE
        # ============================================================

        # Construct development only after the live Values and Preferences
        # objects exist, then wire those exact authoritative instances into it.
        self.personality_development = PersonalityDevelopment(
            personality=self.personality,
        )
        self._wire_personality_development()

        # This store is intentionally unconfigured in plain Mary().  The
        # canonical persistent runtime enables it explicitly after construction.
        self.developed_self_state = DevelopedSelfStateStore(
            personality=self.personality,
            values=self.values,
            preferences=self.preferences,
            personality_development=self.personality_development,
        )

        # Preference-development evidence remains separate from Mary's
        # represented Preferences until an explicit promotion path approves it.
        # Plain Mary() keeps this ledger in memory only; persistent runtimes
        # configure its own tentative-evidence file explicitly.
        self.preference_promotion = PreferencePromotionSystem(limits=self.config.governance)

        # ============================================================
        # SELF MODEL
        # ============================================================

        self.self_model = SelfModel(
            name="Mary",
            personality=self.personality,
            character=self.character,
            values=self.values,
            preferences=self.preferences,
        )

        # ============================================================
        # BIOGRAPHY
        # ============================================================

        self.biography = create_default_biography()

        # ============================================================
        # SELF-FACT PROVENANCE
        # ============================================================

        # This is a read-only projection over Mary's existing self systems.
        # It does not become another identity database.  Its job is to make
        # the boundary between canonical/developed state and temporary model
        # improvisation explicit to cognition.
        self.self_provenance = SelfProvenance(
            biography=self.biography,
            personality=self.personality,
            character=self.character,
            values=self.values,
            preferences=self.preferences,
            personality_development=self.personality_development,
        )

        # ============================================================
        # RELATIONSHIP
        # ============================================================

        self.relationship = RelationshipManager(
            path=self.config.paths.relationship / "relationship.json",
            limits=self.config.governance,
        )
        self.relationship.load()

        # Keep one authoritative creator model and expose the existing
        # relationship components through Mary for compatibility.
        self.user_model = self.relationship.user_model
        self.relationship_history = self.relationship.history
        self.relationship_understanding = self.relationship.understanding
        self.relationship_milestones = self.relationship.milestones

        # Ordinary conversation may contain clear creator facts.  This gate is
        # deliberately conservative and never calls an LLM or writes state on
        # its own; accepted candidates are handed to the existing relationship
        # system so there remains only one authoritative creator model.
        self.natural_relationship_learning = NaturalRelationshipLearner()

        self.creator_directives = CreatorDirectiveSystem(
            path=self.config.paths.relationship / "creator_directives.json",
            capacity=self.config.governance.creator_directive_capacity,
            content_limit=self.config.governance.agency_text_characters,
            backup_generations=self.config.governance.backup_generations,
        )
        self.creator_directives.load()

        # ============================================================
        # LLM
        # ============================================================

        self.llm = self._create_llm_router()
        self.runtime_environment = RuntimeEnvironment(config=self.config, router=self.llm)
        self.runtime_introspection = RuntimeIntrospection()

        # ============================================================
        # REALTIME / DISTRIBUTED CAPABILITY FOUNDATION (13.1)
        # ============================================================

        # Realtime coordination is ephemeral process state. It gives text,
        # speech, future streaming audio, perception, and background events one
        # interruption/attention vocabulary without becoming another memory or
        # identity owner.
        self.realtime = RealtimeInteractionCoordinator()

        # Compute nodes are replaceable resources. 13.1 registers the current
        # host only; the same registry is ready for a later secure cloud/home
        # node transport without moving Mary's identity into a machine record.
        self.node_registry = NodeRegistry.with_local_runtime(self.runtime_environment)

        # Perception providers must describe before Mary interprets. Raw frames
        # are never stored by this boundary and observations enter the same
        # bounded attention bus as other realtime context.
        self.perception_director = PerceptionDirector(self.realtime.attention)

        # Ephemeral runtime metadata only. This is intentionally not persisted:
        # it records which provider/model generated the most recent successful
        # model-backed turn in this process so Mary can answer runtime questions
        # without asking a model to guess about itself.
        self._last_generation_metadata: dict[str, Any] | None = None

        # ============================================================
        # ORCHESTRATION / EPHEMERAL TASK WORKSPACE
        # ============================================================

        # The task workspace is deliberately process-local. It gives future
        # orchestration a structured place for hypotheses, evidence, model
        # consultations, and decisions without turning temporary reasoning into
        # durable memory, creator facts, or developed-self state.
        self.task_workspace = TaskWorkspaceManager(
            limits=self.config.governance,
            on_evict=self.llm.resource_governor.forget_task,
        )
        self.expert_consultant = ExpertConsultant(
            router=self.llm,
            workspace=self.task_workspace,
        )
        self.task_orchestrator = TaskOrchestrator(
            workspace=self.task_workspace,
            router=self.llm,
        )
        self.task_executor = OrchestrationExecutor(
            router=self.llm,
            workspace=self.task_workspace,
            expert=self.expert_consultant,
        )

        # ============================================================
        # TOOLS
        # ============================================================

        self.tools = ToolManager(
            workspace_root=self.config.paths.workspace,
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

        # Conversation engagement governs how much room a thread receives.
        # It is deterministic and separate from identity/memory authority.
        self.engagement = ConversationEngagement()

        # ============================================================
        # EXPRESSION
        # ============================================================

        self.emotion = EmotionManager()

        self.response = ResponseBuilder()

        self.dialogue = DialogueManager(
            max_history=self.config.governance.dialogue_history_capacity,
        )

        self.expression = ExpressionSystem(
            emotion=self.emotion,
            response=self.response,
            dialogue=self.dialogue,
        )

        self.emotion_appraiser = ConversationEmotionAppraiser(
            creator_name=str(
                self.user_model.name or self.identity.creator or "Unbe"
            ).title(),
        )

        # Shared deterministic performance direction for TTS + avatar.  This
        # colors delivery from Mary's represented state without requiring a
        # second model call or inferring the creator's hidden emotions.
        self.expression_director = ExpressionDirector()

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

        self.learner = Learner(
            capacity=self.config.governance.learning_event_capacity,
            text_limit=self.config.governance.process_text_characters,
        )

        self.evaluator = Evaluator(
            llm=self.llm,
            capacity=self.config.governance.evaluation_capacity,
            text_limit=self.config.governance.process_text_characters,
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
            request_capacity=self.config.governance.research_request_capacity,
            result_capacity=self.config.governance.research_result_capacity,
            text_limit=self.config.governance.process_text_characters,
        )

        # ============================================================
        # KNOWLEDGE
        # ============================================================

        self.learning_knowledge = LearningKnowledge(
            capacity=self.config.governance.knowledge_candidate_capacity,
            text_limit=self.config.governance.process_text_characters,
        )

        self.knowledge = KnowledgeManager(
            capacity=self.config.governance.knowledge_concept_capacity,
            source_capacity=self.config.governance.knowledge_source_capacity,
            text_limit=self.config.governance.process_text_characters,
        )

        # The persistence adapter owns only serialization I/O. Candidate state
        # remains owned by LearningKnowledge and long-term concepts remain owned
        # by KnowledgeManager.
        self.knowledge_state = KnowledgeStateStore(
            candidates=self.learning_knowledge,
            knowledge=self.knowledge,
        )

        self.knowledge_learning = KnowledgeLearningBridge(
            candidates=self.learning_knowledge,
            knowledge=self.knowledge,
            learner=self.learner,
            on_change=self.knowledge_state.changed,
        )

        # ============================================================
        # MEMORY
        # ============================================================

        self.memory = MemoryManager(
            limits=self.config.governance,
        )
        self._last_shared_work_learning: dict[str, Any] = {
            "detected": False,
            "recorded": False,
            "reason": "no_shared_work_event_yet",
        }
        self._last_memory_recall_trace: dict[str, Any] = {}

        # Build structured creator understanding from older explicit memories
        # using only the relationship manager's narrow high-confidence parser.
        self._sync_relationship_from_existing_memories()

        # ============================================================
        # COGNITION
        # ============================================================

        # One authoritative turn-routing policy sits above provider routing.
        # It decides whether a model-backed turn is personal Mary conversation
        # (local-first) or detached task/general work (free cloud first).
        self.turn_policy = TurnPolicyEngine()

        self.reasoning = ReasoningEngine(
            llm=self.llm,
            evidence_validator=self.evidence_validator,
            turn_policy=self.turn_policy,
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

        self.agency = Agency(
            limits=self.config.governance,
            storage_root=self.config.paths.goals,
        )
        self.agency.load()

        # Creator directives are the durable source of creator-directed
        # agency orientation. Reconcile them into curiosity state on every
        # startup so a missing/older derived curiosity file cannot silently
        # erase an active creator directive.
        self._sync_creator_directives_to_agency()

        self.relationship_curiosity = RelationshipCuriosityDevelopment(
            relationship=self.relationship,
            curiosity_system=self.agency.curiosities,
            creator_name=str(self.user_model.name or self.identity.creator or "Unbe").title(),
        )
        self.relationship_curiosity.sync()
        self.conversation_learning = ConversationLearningBridge(
            self.relationship_curiosity
        )
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
            preferences=self.preferences,
            character=self.character,
            user_model=self.user_model,
            creator_directives=self.creator_directives,
            agency=self.agency,
            autonomy=self.autonomy,
            tools=self.tools,
            emotion=self.emotion,
        )

        # ============================================================
        # UNIFIED TURN MIND STATE
        # ============================================================

        self.turn_mind = TurnMindStateBuilder(
            identity=self.identity,
            self_model=self.self_model,
            biography=self.biography,
            personality=self.personality,
            character=self.character,
            values=self.values,
            preferences=self.preferences,
            self_provenance=self.self_provenance,
            relationship=self.relationship,
            knowledge=self.knowledge,
            learner=self.learner,
            agency=self.agency,
            autonomy=self.autonomy,
            tools=self.tools,
            emotion=self.emotion,
            dialogue=self.dialogue,
        )

        # Active dialogue history remains owned by DialogueManager. The context
        # lifecycle chooses only the bounded slice that cognition should send to
        # an LLM on each turn; it never creates durable memory by itself.
        self.context_lifecycle = ConversationContextLifecycle(
            max_turns=self.config.governance.context_turns,
            max_characters=self.config.governance.context_characters,
            max_message_characters=self.config.governance.context_message_characters,
            max_anchors=self.config.governance.context_anchors,
        )

        # Conversation continuity is owned by the TurnMind builder so there is
        # only one authoritative drive/question-budget implementation.
        self.continuity = self.turn_mind.continuity
        self.performance = self.turn_mind.performance

        # ============================================================
        # LOCAL CHARACTER MIND / COGNITIVE RESERVOIR
        # ============================================================

        # Starts in-memory so plain Mary() remains side-effect-light for tests.
        # The canonical persistent application configures a rebuildable SQLite
        # reservoir beside Mary's data tree after durable state has loaded.
        self.mind = CharacterMind(self)

        # Read-only architecture contract: proves that the subsystems above still
        # share one router/emotion/authority layout after integration changes.
        self.system_contract = MarySystemContract()

        # Post-turn development closes the loop from grounded experience to
        # safe memory consolidation, milestones, and strictly evidenced self
        # development. It never treats model dialogue as durable self evidence.
        self.growth = GrowthEngine(self)

        # Explicit creator ratings are kept in a separate private evaluation
        # dataset for future Mary-specific model evaluation/training. Merely
        # talking to Mary never creates a training record, and feedback is not
        # identity/memory/development authority.
        self.training_feedback = ResponseFeedbackStore()

    # ================================================================
    # PRIMARY ENTRY POINT
    # ================================================================

    def process(
        self,
        input_text: str,
        *,
        turn_context: dict[str, Any] | None = None,
        workspace_context: dict[str, Any] | None = None,
    ) -> CognitiveCycleResult:
        """
        Process one complete MaryV2 interaction.
        """

        input_text = self._normalize_input(
            input_text
        )

        # Capture the conversation that existed *before* this turn so the
        # current user message is not duplicated in LLM context.
        session_history = self.dialogue.messages_for_llm(
            limit=None
        )

        intent = self._detect_intent(
            input_text
        )

        engagement_plan = self.engagement.begin_turn(
            input_text,
            intent_name=intent.intent_type.value,
        )

        # Learn only clear, naturally volunteered creator facts before context
        # assembly.  This lets the same turn see the updated creator model while
        # preserving the normal conversational response path.  Explicit memory/
        # relationship/tool/system intents keep their existing dedicated paths.
        natural_relationship_learning = self._learn_natural_relationship_share(
            input_text,
            intent=intent,
        )
        self.conversation_learning.observe_learning(
            natural_relationship_learning
        )
        shared_work_learning = self._learn_shared_work_statement(
            input_text,
            intent=intent,
        )
        if shared_work_learning is not None:
            self._last_shared_work_learning = dict(shared_work_learning)

        if natural_relationship_learning is not None:
            memory_event = dict(natural_relationship_learning)
            memory_event["operation"] = "natural_relationship_learning"
            memory_event["stored"] = bool(memory_event.get("memory_id"))
            memory_event["relationship_committed"] = bool(
                memory_event.get("learned") or memory_event.get("already_known")
            )
            self.memory.record_lifecycle_event(memory_event)

        # A real curiosity question remains process-local conversation state long
        # enough for natural follow-ups such as ``why that question?``. Resolve
        # that locally before asking a provider to guess why Mary asked it.
        learning_followup = self.conversation_learning.respond_to_pending_followup(
            input_text
        )

        # When the creator explicitly invites Mary to ask/learn, use Mary's real
        # structured relationship-curiosity gaps instead of letting an LLM invent
        # a generic question. This is deterministic and never autonomously asks.
        learning_invitation = (
            None
            if learning_followup is not None
            else self.conversation_learning.respond_if_invited(input_text)
        )

        # Appraise the incoming creator turn before generation without mutating
        # Mary's durable/current emotion state yet. This lets relational warmth,
        # concern, pride, etc. color the *current* response instead of arriving a
        # full turn late. The completed-turn appraisal below remains authoritative
        # for actually updating the bounded emotion manager.
        incoming_emotion_appraisal = self.emotion_appraiser.appraise(
            input_text=input_text,
            response_text="",
            intent=intent,
        )

        incoming_emotion_payload: dict[str, Any] | None = None
        if (
            incoming_emotion_appraisal.relationship_relevance >= 0.85
            or incoming_emotion_appraisal.source != "intent"
        ):
            incoming_emotion_payload = incoming_emotion_appraisal.to_dict()

        # Realtime sources (perception, presence, tools, future node events) may
        # have meaningful pending context. Claim only a tiny high-value window
        # for this turn. These events remain explicitly context-only and never
        # gain creator/memory authority by entering the prompt.
        try:
            attention_events = self.realtime.attention.claim_context(
                limit=2,
                minimum_importance=0.6,
            )
        except Exception:
            attention_events = []

        context = self._build_context(
            input_text,
            intent=intent,
            recent_conversation=session_history,
            incoming_emotion_appraisal=incoming_emotion_payload,
            workspace_context=workspace_context,
        )

        # Transport/session metadata is context-only. It never becomes Mary's
        # identity, memory, relationship, or other durable state authority.
        attach_turn_envelope(
            context,
            turn_context,
        )

        mind_state = context.setdefault("mind_state", {})
        mind_state["conversation_engagement"] = engagement_plan.to_dict()
        if attention_events:
            runtime_context = mind_state.setdefault("runtime_context", {})
            if isinstance(runtime_context, dict):
                runtime_context["attention_context"] = [
                    {
                        "source": event.source.value,
                        "summary": event.summary[:280],
                        "importance": round(float(event.importance), 3),
                        "authority": "context_only",
                    }
                    for event in attention_events
                ]
        if engagement_plan.effective_mode in {"engaged", "deep"}:
            try:
                unresolved = list(self.relationship_curiosity.unresolved_gaps())
            except Exception:
                unresolved = []
            if unresolved:
                gap = dict(unresolved[0])
                mind_state["conversation_initiative"] = {
                    "permission": "proactive_within_current_thread",
                    "grounded_gap": {
                        key: gap.get(key)
                        for key in ("category", "description", "question", "status", "source")
                        if gap.get(key) not in (None, "", [], {})
                    },
                    "guidance": (
                        "Mary may ask one specific question that advances this represented gap when it fits the flow; "
                        "react to the creator's answer first and do not conduct an interview."
                    ),
                }
        # From this point forward, "recent_conversation" means the bounded
        # LLM-facing window selected by the context lifecycle, not the entire
        # in-session transcript.
        recent_conversation = list(context.get("conversation", []))

        self.dialogue.begin_turn(
            input_text,
            metadata={
                "intent": intent.intent_type.value,
            },
        )
        self.dialogue.begin_thinking()

        system_response: str | None = None
        external_knowledge: list[Any] = []
        external_sources: list[dict[str, Any]] = []
        skip_cognition = False

        if learning_followup is not None:
            system_response = str(learning_followup.get("response", "")).strip()
            skip_cognition = bool(system_response)

        elif learning_invitation is not None:
            system_response = str(learning_invitation.get("response", "")).strip()
            skip_cognition = bool(system_response)

        elif intent.intent_type == IntentType.RELATIONSHIP_SHARE:
            relationship_action = self._handle_relationship_share(intent)
            system_response = relationship_action.get("system_response")
            skip_cognition = True

        elif intent.intent_type == IntentType.RELATIONSHIP_QUERY:
            relationship_action = self._handle_relationship_query(
                intent,
                recent_conversation=session_history,
            )
            system_response = relationship_action.get("system_response")
            skip_cognition = True

        elif intent.intent_type == IntentType.CONVERSATION_RECALL:
            system_response = self._handle_conversation_recall(
                recent_conversation,
                recall_scope=str(intent.parameters.get("recall_scope", "recent_dialogue")),
            )
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
                intent,
                incoming_emotion_appraisal=incoming_emotion_payload,
            )
            system_response = self_action.get(
                "system_response"
            )
            external_knowledge = list(
                self_action.get(
                    "knowledge",
                    [],
                )
            )
            skip_cognition = bool(
                self_action.get(
                    "skip_cognition",
                    False,
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
            elif action == "llm_control":
                tool_action = self._handle_llm_control(
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
                IntentType.CONVERSATION_RECALL,
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
            if natural_relationship_learning is not None:
                metadata["natural_relationship_learning"] = dict(
                    natural_relationship_learning
                )
            if shared_work_learning is not None:
                metadata["shared_work_learning"] = dict(shared_work_learning)
            if learning_followup is not None:
                metadata["conversation_learning_followup"] = {
                    "handled": True,
                    "category": learning_followup.get("category"),
                    "pending_id": learning_followup.get("pending_id"),
                    "llm_calls_after_action": 0,
                }
            if learning_invitation is not None:
                metadata["conversation_learning_invitation"] = {
                    "handled": True,
                    "category": learning_invitation.get("category"),
                    "pending_id": learning_invitation.get("pending_id"),
                    "llm_calls_after_action": 0,
                }
            if system_action == "propose_code_change":
                metadata.update({
                    "handled_by": "mary_code_change_planner",
                    "llm_calls_after_planning": 0,
                })

            cycle = self._build_system_cycle_result(
                input_text=input_text,
                intent=intent,
                response=system_response,
                context=context,
                metadata=metadata,
            )
            return self._finalize_turn(
                input_text=input_text,
                result=cycle,
            )

        # Before spending a provider call, give Mary's always-running local
        # character mind a chance to answer from represented state.  This path
        # is intentionally narrow: reflexes, represented status, and high-
        # confidence local facts. Novel language still escalates to cognition.
        try:
            local_mind_result = self.mind.try_respond(
                input_text,
                intent=intent,
                context=context,
            )
        except Exception as exc:
            local_mind_result = None
            local_mind_error = f"{type(exc).__name__}: {exc}"
        else:
            local_mind_error = None

        if local_mind_result is not None and local_mind_result.handled:
            safe_local = safe_local_metadata(local_mind_result.metadata)
            cycle = self._build_system_cycle_result(
                input_text=input_text,
                intent=intent,
                response=local_mind_result.response,
                context=context,
                metadata={
                    "handled_by": "mary_local_mind",
                    "local_mind": safe_local,
                    "llm_calls_after_action": 0,
                },
            )
            cycle.reasoning.reasoning_type = "local_character_mind"
            apply_local_cycle_metadata(cycle, local_mind_result.metadata)
            cycle.reflection.metadata.update({
                "mode": "local_mind_no_model",
                "llm_calls": 0,
            })
            return self._finalize_turn(input_text=input_text, result=cycle)

        if local_mind_error:
            context.setdefault("mind_state", {}).setdefault("local_mind", {})["error"] = local_mind_error
        elif local_mind_result is not None:
            # Only bounded control-plane fields enter cognition.  Canonical plan
            # semantics and selected fact values remain inside the local mind.
            context.setdefault("mind_state", {})["local_mind"] = safe_local_metadata(
                local_mind_result.metadata
            )

        result = self.cognition.process(
            input_text=input_text,
            intent=intent,
            conversation=context.get("conversation", []),
            memories=context["memory"].get(
                "relevant_memories",
                [],
            ),
            knowledge=external_knowledge,
            user_context=context["user"],
            personality_context=context["personality"],
            active_goals=context.get("mind_state", {}).get(
                "agency", {}
            ).get("active_goals", []),
            mind_state=context.get("mind_state", {}),
        )

        if local_mind_result is not None and not local_mind_result.handled:
            merge_escalated_cycle_metadata(result, local_mind_result.metadata)

        if natural_relationship_learning is not None:
            result.metadata["natural_relationship_learning"] = dict(
                natural_relationship_learning
            )
        if shared_work_learning is not None:
            result.metadata["shared_work_learning"] = dict(shared_work_learning)

        expert_items = [
            item for item in external_knowledge
            if isinstance(item, dict) and item.get("expert_consultation") is True
        ]
        if expert_items:
            expert_item = dict(expert_items[-1])
            expert_meta = {
                "provider": expert_item.get("provider"),
                "model": expert_item.get("model"),
                "paid": True,
                "advisory_only": True,
                "usage": dict(expert_item.get("usage", {}) or {}),
            }
            result.metadata["expert_consultation"] = expert_meta
            try:
                result.reasoning.metadata["expert_consultation"] = dict(expert_meta)
            except Exception:
                pass

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

        return self._finalize_turn(
            input_text=input_text,
            result=result,
        )

    def _finalize_turn(
        self,
        *,
        input_text: str,
        result: CognitiveCycleResult,
    ) -> CognitiveCycleResult:
        """Apply expression state and commit the completed turn to dialogue."""

        result = self._apply_conversation_emotion(
            input_text=input_text,
            result=result,
        )

        # One deterministic performance plan drives both voice and avatar so
        # expression is coherent instead of each surface guessing separately.
        try:
            reasoning_meta = dict(getattr(result.reasoning, "metadata", {}) or {})
            lane_data = dict(reasoning_meta.get("conversation_lane", {}) or {})
            local_meta = dict(result.metadata.get("local_mind", {}) or {})
            local_plan = dict(local_meta.get("plan", {}) or {})
            delivery = self.expression_director.plan(
                input_text=input_text,
                response_text=result.final_response,
                emotional_state=self.emotion.state,
                conversation_lane=str(lane_data.get("lane") or "conversation"),
                dialogue_act=str(local_plan.get("act") or ""),
            )
            result.metadata["delivery_plan"] = delivery.to_dict()
        except Exception as exc:
            result.metadata["delivery_plan_error"] = f"{type(exc).__name__}: {exc}"

        try:
            response = self.expression.build_response(
                result.final_response,
                emotional_state=self.emotion.state,
                directed_to=str(
                    self.user_model.name or self.identity.creator or "Unbe"
                ).title(),
                metadata_extra={
                    "intent": (
                        result.intent.intent_type.value
                        if result.intent is not None
                        else "unknown"
                    ),
                    "reflection_mode": result.reflection.metadata.get("mode"),
                    "delivery_plan": dict(result.metadata.get("delivery_plan", {}) or {}),
                    "conversational_drive": (
                        result.context.mind_state.get("continuity", {}).get("drive")
                        if isinstance(result.context.mind_state, dict)
                        else None
                    ),
                },
            )
            self.expression.record_response(response)
            self.dialogue.finish_turn()
            result.metadata["dialogue_turn"] = self.dialogue.state.turn_number
            result.metadata["dialogue_recorded"] = True
        except Exception as exc:
            # Dialogue continuity should enrich cognition, never prevent a valid
            # grounded response from reaching the creator.
            result.metadata["dialogue_recorded"] = False
            result.metadata["dialogue_error"] = f"{type(exc).__name__}: {exc}"

        try:
            conversation_state = (
                result.context.mind_state.get("conversation", {})
                if isinstance(result.context.mind_state, dict)
                else {}
            )
            lifecycle = (
                conversation_state.get("lifecycle", {})
                if isinstance(conversation_state, dict)
                else {}
            )
            if isinstance(lifecycle, dict) and lifecycle:
                result.metadata["context_lifecycle"] = dict(lifecycle)
        except Exception:
            pass

        try:
            reasoning_metadata = dict(
                getattr(result.reasoning, "metadata", {}) or {}
            )
            provider = reasoning_metadata.get("provider")
            if (
                provider
                and not reasoning_metadata.get("llm_skipped", False)
                and not reasoning_metadata.get("llm_unavailable", False)
            ):
                self._last_generation_metadata = {
                    "provider": provider,
                    "model": reasoning_metadata.get("model"),
                    "finish_reason": reasoning_metadata.get("finish_reason"),
                    "usage": dict(reasoning_metadata.get("usage", {}) or {}),
                }
        except Exception:
            pass

        try:
            self.mind.observe_completed_turn(result)
        except Exception as exc:
            result.metadata["local_mind_observe_error"] = f"{type(exc).__name__}: {exc}"

        try:
            self.engagement.complete_turn(result.final_response)
            result.metadata["conversation_engagement"] = self.engagement.status()
        except Exception as exc:
            result.metadata["conversation_engagement_error"] = f"{type(exc).__name__}: {exc}"

        try:
            result.metadata["growth"] = self.growth.observe_turn(
                input_text=input_text,
                result=result,
            )
        except Exception as exc:
            result.metadata["growth_error"] = f"{type(exc).__name__}: {exc}"

        return result

    def _apply_conversation_emotion(
        self,
        *,
        input_text: str,
        result: CognitiveCycleResult,
    ) -> CognitiveCycleResult:
        """Appraise one completed turn using Mary's existing emotion state."""

        appraisal = self.emotion_appraiser.appraise(
            input_text=input_text,
            response_text=result.final_response,
            intent=result.intent,
        )
        state = self.emotion_appraiser.apply(
            self.emotion,
            appraisal,
        )
        result.metadata["emotion_appraisal"] = appraisal.to_dict()
        result.metadata["emotional_state"] = state.to_dict()
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
        *,
        intent: Intent | None = None,
        recent_conversation: list[dict[str, str]] | None = None,
        incoming_emotion_appraisal: dict[str, Any] | None = None,
        workspace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build one integrated cognitive context from Mary's real subsystems."""

        memory_context = self.memory.build_context(
            input_text
        )

        lifecycle_window = self.context_lifecycle.select(
            recent_conversation or []
        )
        conversation = [
            dict(item)
            for item in lifecycle_window.messages
        ]
        lifecycle_context = lifecycle_window.to_dict()

        model_memories = [
            item
            for item in list(memory_context.get("relevant_memories", []))
            if not (
                isinstance(item, dict)
                and text_has_test_probe_marker(str(item.get("content", "")))
            )
        ]
        model_memory_context = dict(memory_context)
        model_memory_context["relevant_memories"] = model_memories

        mind_state = self.turn_mind.build(
            input_text=input_text,
            intent=intent,
            relevant_memories=model_memories,
            recent_conversation=conversation,
            context_lifecycle=lifecycle_context,
            incoming_emotion_appraisal=incoming_emotion_appraisal,
            workspace_context=workspace_context,
        )
        prompt_mind_state = mind_state.prompt_view()
        relationship_view = prompt_mind_state.get("relationship")
        if not isinstance(relationship_view, dict):
            relationship_view = {}
            prompt_mind_state["relationship"] = relationship_view
        relationship_view["shared_history"] = self._shared_history_context(
            recent_conversation or []
        )
        pending_question = self.conversation_learning.prompt_view()
        if pending_question is not None:
            relationship_view["pending_curiosity_question"] = pending_question

        # Bounded derived reservoir hits can enrich a model-backed turn without
        # turning the reservoir into an authority.  Each hit carries provenance
        # and confidence, and the entire reservoir can be rebuilt from canonical
        # Mary state.
        try:
            reservoir_hits = self.mind.prompt_hits(input_text, limit=5)
        except Exception:
            reservoir_hits = []
        if reservoir_hits:
            prompt_mind_state["cognitive_reservoir"] = {
                "hits": reservoir_hits,
                "semantics": "derived local retrieval; canonical state outranks this projection",
            }

        # Hybrid personal/runtime turns remain Mary conversation, but the model
        # receives a tiny authoritative host snapshot so it can react naturally
        # without inventing where it is running or which providers are usable.
        if is_personal_runtime_reaction(input_text):
            runtime = self.runtime_environment.snapshot()
            prompt_mind_state["runtime_context"] = {
                "host_type": runtime.get("host_type"),
                "platform": runtime.get("platform"),
                "effective_conversation_route": list(runtime.get("effective_conversation_route", []) or []),
                "effective_task_route": list(runtime.get("effective_task_route", []) or []),
                "available_providers": [
                    name
                    for name, data in dict(runtime.get("providers", {}) or {}).items()
                    if bool(dict(data or {}).get("available"))
                ],
                "unavailable_providers": [
                    name
                    for name, data in dict(runtime.get("providers", {}) or {}).items()
                    if bool(dict(data or {}).get("configured"))
                    and not bool(dict(data or {}).get("available"))
                ],
                "guidance": (
                    "Use these runtime facts only as grounded context. Answer as Mary in normal conversation; "
                    "do not recite a diagnostic report unless the creator explicitly asks for one."
                ),
            }

        return {
            "memory": model_memory_context,
            "user": self._user_context_for_model(),
            "personality": self._personality_context(),
            "conversation": conversation,
            "context_lifecycle": lifecycle_context,
            "mind_state": prompt_mind_state,
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

        intent = self.cognition.detect_intent(
            input_text
        )

        # Pronoun follow-up after an explicit route change: "you are using it
        # aren't you?" should report runtime truth rather than let a model guess.
        override = (
            self.llm.session_override_status()
            if callable(getattr(self.llm, "session_override_status", None))
            else {"provider": None, "route": None}
        )
        normalized = normalize_for_matching(input_text)
        if (override.get("provider") or override.get("route")) and any(
            phrase in normalized
            for phrase in (
                "are you using it", "are u using it", "you are using it arent you",
                "you are using it aren't you", "ur using it arent you", "using it now",
            )
        ):
            return Intent(
                intent_type=IntentType.SELF_QUERY,
                confidence=0.99,
                description="Creator asks whether the active model-route override is actually in use.",
                parameters={
                    "query": input_text,
                    "self_query_type": "runtime_architecture",
                },
                source="runtime_route_followup",
            )

        return intent

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
    # RECENT CONVERSATION RECALL
    # ================================================================

    def _shared_history_context(
        self,
        recent_conversation: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Build a bounded creator-grounded view of Mary/Unbe shared work.

        Assistant-role dialogue is never evidence here. The view is intentionally
        small and model-facing: it exists so phrases such as ``everything we've
        done`` can refer to a real shared project without forcing Mary into the
        opposite error of denying all shared history.
        """

        work_markers = (
            "maryv2", "working on", "work on", "building", "build ", "project",
            "developing", "fixing", "testing", "debugging", "implementing",
            "finish ", "finishing ", "provider", "ollama",
        )

        items: list[str] = []

        def add(value: Any) -> None:
            text = " ".join(str(value or "").split())
            if not text or text_has_test_probe_marker(text):
                return
            lowered = text.lower()
            if not any(marker in lowered for marker in work_markers):
                return
            if len(text) > 220:
                text = text[:219].rstrip() + "…"
            if text not in items:
                items.append(text)

        for entry in recent_conversation[-10:]:
            if not isinstance(entry, dict) or str(entry.get("role", "")) != "user":
                continue
            add(entry.get("content", ""))
            if len(items) >= 3:
                break

        try:
            profile = self._creator_profile_for_conversation()
        except Exception:
            profile = {}
        for goal in profile.get("goals", []) if isinstance(profile, dict) else []:
            add(goal)

        if len(items) < 4:
            for memory in reversed(self._all_available_memories()):
                if not self._memory_is_creator_owned(memory):
                    continue
                add(self._memory_to_text(memory))
                if len(items) >= 4:
                    break

        project_name = None
        if any("maryv2" in item.lower() for item in items):
            project_name = "MaryV2"

        return {
            "project": project_name,
            "grounded_threads": items[:4],
            "current_runtime_contract": getattr(self.system_contract, "VERSION", None),
            "evidence_policy": "user-role dialogue + creator-owned durable state only; assistant-role dialogue excluded",
        }

    def _handle_conversation_recall(
        self,
        recent_conversation: list[dict[str, str]],
        *,
        recall_scope: str = "recent_dialogue",
    ) -> str:
        """Recall recent dialogue concisely without dumping whole prior replies."""

        messages = [
            {
                "role": str(item.get("role", "")),
                "content": str(item.get("content", "")).strip(),
            }
            for item in recent_conversation[-8:]
            if isinstance(item, dict) and str(item.get("content", "")).strip()
        ]
        # Shared-work continuity may be grounded by durable creator/project
        # state even when this fresh process has no session turns yet.
        if not messages and str(recall_scope).strip().lower() != "shared_work":
            return "We haven't built up any recent conversation in this session yet."

        user_messages = [item["content"] for item in messages if item["role"] == "user"]
        mary_messages = [item["content"] for item in messages if item["role"] == "assistant"]

        latest_user = user_messages[-1] if user_messages else None
        earlier_user = user_messages[-2] if len(user_messages) >= 2 else None
        latest_mary = mary_messages[-1] if mary_messages else None

        if str(recall_scope).strip().lower() == "shared_work":
            work_markers = (
                "working on", "work on", "building", "build ", "project",
                "developing", "fixing", "testing", "debugging", "implementing",
                "finish ", "finishing ",
            )
            grounded_work = [
                text
                for text in user_messages
                if any(marker in text.lower() for marker in work_markers)
            ]
            if grounded_work:
                latest = grounded_work[-1]
                if len(latest) > 220:
                    latest = latest[:219].rstrip() + "…"
                return (
                    "From what you've actually said in this session, the clearest "
                    f"shared-work thread is ‘{latest}’."
                )

            # Session dialogue is not the only legitimate continuity source.
            # Durable creator goals and creator-owned episodic/semantic memories may
            # identify an ongoing project, but Mary's own assistant-role dialogue is
            # never used as evidence here.
            durable_work: list[str] = []
            try:
                profile = self._creator_profile_for_conversation()
            except Exception:
                profile = {}
            for goal in profile.get("goals", []) if isinstance(profile, dict) else []:
                value = " ".join(str(goal).split())
                if value and value not in durable_work:
                    durable_work.append(value)

            for memory in reversed(self._all_available_memories()):
                if not self._memory_is_creator_owned(memory):
                    continue
                text = self._memory_to_text(memory)
                if text_has_test_probe_marker(text):
                    continue
                lowered_text = text.lower()
                if text and any(marker in lowered_text for marker in work_markers):
                    compact_text = text if len(text) <= 220 else text[:219].rstrip() + "…"
                    if compact_text not in durable_work:
                        durable_work.append(compact_text)
                if len(durable_work) >= 3:
                    break

            if durable_work:
                lead = durable_work[0]
                return (
                    "The clearest ongoing thing I have grounded in your durable creator "
                    f"state is {lead}. I can use that as our project continuity without "
                    "pretending one of my own improvised replies was something you told me."
                )

            return (
                "I don't have a grounded shared-work item in this session or your durable "
                "creator/project state yet. I shouldn't turn something from one of my own "
                "earlier replies into a project we supposedly worked on together."
            )

        def compact(text: str | None, limit: int = 180) -> str:
            value = " ".join(str(text or "").split())
            if len(value) <= limit:
                return value
            return value[: limit - 1].rstrip() + "…"

        parts: list[str] = []
        if earlier_user:
            parts.append(f"you asked about ‘{compact(earlier_user, 120)}’")
        if latest_user:
            parts.append(f"then ‘{compact(latest_user, 120)}’")

        if parts:
            response = "We were just talking about this: " + ", ".join(parts) + "."
        elif latest_user:
            response = f"The most recent thing you said was ‘{compact(latest_user, 160)}’."
        else:
            response = "I remember the recent exchange, but there isn't a recent creator turn to quote."

        if latest_mary:
            response += f" My last reply was basically: ‘{compact(latest_mary, 220)}’"

        return response

    # ================================================================
    # RELATIONSHIP DEVELOPMENT
    # ================================================================

    def _learn_natural_relationship_share(
        self,
        input_text: str,
        *,
        intent: Intent | None,
    ) -> dict[str, Any] | None:
        """Silently learn a clear creator fact from ordinary conversation.

        Natural learning is intentionally narrower than explicit
        ``learn this about me:``. The deterministic gate only recognizes
        direct first-person creator statements.

        RelationshipManager remains authoritative for parsing, supersession,
        history, deduplication, and persistence.

        The relationship parser supports an evidence-less preview. A durable
        relationship write follows the same proven transaction used by
        explicit creator learning:

            parse/validate
                -> preserve creator-owned episodic evidence
                -> learn_explicit(..., evidence_id=<memory id>)

        This prevents a parse-only result from being mistaken for committed
        creator state.
        """

        if intent is None:
            return None

        intent_name = str(
            getattr(intent.intent_type, "value", intent.intent_type)
        ).strip().lower()

        if intent_name not in {
            "conversation",
            "goal",
            "request",
        }:
            return None

        candidate = self.natural_relationship_learning.detect(
            input_text
        )
        if candidate is None:
            return None

        content = str(
            candidate.get("content", "")
        ).strip()
        if not content:
            return None
        match_content = str(
            candidate.get("match_content", "")
        ).strip()

        # ------------------------------------------------------------
        # PARSE / DEDUP PREVIEW
        # ------------------------------------------------------------
        #
        # RelationshipManager.preview_explicit() is deliberately pure: it
        # classifies the creator share and checks semantic duplication without
        # writing profile/history/observation state.
        parse_content = content
        try:
            preview = self.relationship.preview_explicit(
                parse_content,
                force_general=False,
            )
            # Natural chat shorthand such as ``u``/``dont`` is normalized only
            # for deterministic parsing. The original creator text above is
            # still what becomes evidence and dialogue history.
            if preview is None and match_content and match_content != content.casefold():
                parse_content = match_content
                preview = self.relationship.preview_explicit(
                    parse_content,
                    force_general=False,
                )
        except Exception as exc:
            # Relationship learning should enrich an ordinary conversation,
            # never prevent the conversation from continuing.
            return {
                "detected": True,
                "learned": False,
                "signal_type": candidate.get("signal_type"),
                "reason": "relationship_error",
                "error": f"{type(exc).__name__}: {exc}",
            }

        if preview is None:
            return {
                "detected": True,
                "learned": False,
                "signal_type": candidate.get("signal_type"),
                "reason": "relationship_parser_rejected",
            }

        # If RelationshipManager already has this creator fact, do not
        # create another episodic record and do not advance curiosity again.
        if bool(preview.get("already_known", False)):
            return {
                "detected": True,
                "learned": False,
                "already_known": True,
                "signal_type": candidate.get("signal_type"),
                "category": preview.get("category"),
                "label": preview.get("label"),
                "value": preview.get("value"),
                "memory_id": None,
                "source": "creator_natural",
            }

        # ------------------------------------------------------------
        # PRESERVE EVIDENCE
        # ------------------------------------------------------------
        #
        # This mirrors the explicit relationship-share path: durable
        # structured relationship state is backed by a creator-owned memory
        # record whose ID is supplied to RelationshipManager.
        memory = self.remember(
            content,
            memory_type="episodic",
            importance=0.8,
            metadata={
                "source": "interaction",
                "event_type": "creator_natural_share",
                "owner": "creator",
                "speaker": "Unbe",
                "perspective": "creator_first_person",
                "relationship_source": "creator_natural",
            },
        )

        if memory is None:
            return {
                "detected": True,
                "learned": False,
                "already_known": False,
                "signal_type": candidate.get("signal_type"),
                "category": preview.get("category"),
                "label": preview.get("label"),
                "value": preview.get("value"),
                "memory_id": None,
                "source": "creator_natural",
                "reason": "memory_store_failed",
            }

        memory_id = (
            str(getattr(memory, "id", "") or "").strip()
            or None
        )

        # ------------------------------------------------------------
        # COMMIT STRUCTURED RELATIONSHIP STATE
        # ------------------------------------------------------------
        try:
            learned = self.relationship.learn_explicit(
                parse_content,
                source="creator_natural",
                evidence_id=memory_id,
                force_general=False,
            )
        except Exception as exc:
            return {
                "detected": True,
                "learned": False,
                "already_known": False,
                "signal_type": candidate.get("signal_type"),
                "category": preview.get("category"),
                "label": preview.get("label"),
                "value": preview.get("value"),
                "memory_id": memory_id,
                "source": "creator_natural",
                "reason": "relationship_commit_error",
                "error": f"{type(exc).__name__}: {exc}",
            }

        if learned is None:
            return {
                "detected": True,
                "learned": False,
                "already_known": False,
                "signal_type": candidate.get("signal_type"),
                "category": preview.get("category"),
                "label": preview.get("label"),
                "value": preview.get("value"),
                "memory_id": memory_id,
                "source": "creator_natural",
                "reason": "relationship_commit_rejected",
            }

        already_known = bool(
            learned.get("already_known", False)
        )

        if not already_known:
            self._advance_creator_curiosity(
                learned
            )

        return {
            "detected": True,
            "learned": not already_known,
            "already_known": already_known,
            "signal_type": candidate.get("signal_type"),
            "category": learned.get(
                "category",
                preview.get("category"),
            ),
            "label": learned.get(
                "label",
                preview.get("label"),
            ),
            "value": learned.get(
                "value",
                preview.get("value"),
            ),
            "memory_id": memory_id,
            "source": "creator_natural",
        }

    @staticmethod
    def _render_creator_owned_shared_work(text: Any) -> str:
        """Render creator-authored shared-work evidence from Mary's viewpoint.

        Shared-work history deliberately stores the creator's original wording
        as evidence.  When Mary later speaks that evidence herself, a small
        perspective adjustment prevents phrases such as ``my MacBook`` or
        ``building you`` from being repeated as if Mary originally said them.
        The conversion is intentionally narrow rather than a general rewrite.
        """

        value = " ".join(str(text or "").split()).strip()
        if not value:
            return value

        # Possessives are unambiguous across the creator/Mary boundary.
        placeholders = {
            "__MARYV2_CREATOR_YOUR__": "your",
            "__MARYV2_MARY_MY__": "my",
            "__MARYV2_CREATOR_YOURS__": "yours",
            "__MARYV2_MARY_MINE__": "mine",
        }
        value = re.sub(r"\bmine\b", "__MARYV2_CREATOR_YOURS__", value, flags=re.IGNORECASE)
        value = re.sub(r"\bmy\b", "__MARYV2_CREATOR_YOUR__", value, flags=re.IGNORECASE)
        value = re.sub(r"\byours\b", "__MARYV2_MARY_MINE__", value, flags=re.IGNORECASE)
        value = re.sub(r"\byour\b", "__MARYV2_MARY_MY__", value, flags=re.IGNORECASE)
        for marker, replacement in placeholders.items():
            value = value.replace(marker, replacement)

        # In creator-authored work notes, these positions are object references
        # to Mary, so they can safely become first person when Mary recounts them.
        value = re.sub(
            r"\b(building|developing|fixing|testing|improving|polishing|updating)\s+you\b",
            lambda match: f"{match.group(1)} me",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\b(for|with|to)\s+you\b",
            lambda match: f"{match.group(1)} me",
            value,
            flags=re.IGNORECASE,
        )
        return value

    @staticmethod
    def _shared_work_evidence(text: str, *, allow_test_probe: bool = False) -> str | None:
        """Return a conservative creator-authored shared-work statement.

        Questions about shared work are retrieval requests, not new evidence. A
        mixed turn such as ``we're running on my MacBook ... what do you think``
        keeps the declarative prefix while dropping the trailing question.
        """

        raw = " ".join(str(text or "").split()).strip()
        if not raw or (text_has_test_probe_marker(raw) and not allow_test_probe):
            return None

        normalized = normalize_for_matching(raw)
        question_prefixes = (
            "what ", "why ", "how ", "do ", "does ", "did ", "can ",
            "could ", "would ", "will ", "are ", "is ", "have ", "has ",
            "tell me ", "remind me ",
        )
        if normalized.startswith(question_prefixes):
            return None

        candidate = raw.split("?", 1)[0].strip()
        candidate = re.sub(
            r"^(?:hey|hi)\s+mary[,!]?\s*",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()
        candidate = re.sub(
            r"\s+(?:what do (?:u|you) think|how does that feel|what does (?:that|this) feel like)\s*$",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip(" ,.-")
        candidate_normalized = normalize_for_matching(candidate)
        if len(candidate.split()) < 4:
            return None

        plural_signal = re.search(r"\b(?:we|we're|weve|we've|we have|our|us)\b", candidate_normalized)
        work_signal = re.search(
            r"\b(?:work(?:ing|ed)?|(?:build|building|built)|develop(?:ing|ed)?|fix(?:ing|ed)?|"
            r"test(?:ing|ed)?|run(?:ning)?|port(?:ing|ed)?|install(?:ing|ed)?|set up|"
            r"finish(?:ing|ed)?|complete(?:d|ing)?|ship(?:ping|ped)?|package(?:d|ing)?|"
            r"deploy(?:ing|ed)?|integrat(?:e|ing|ed)|debug(?:ging|ged)?)\b",
            candidate_normalized,
        )
        if plural_signal is None or work_signal is None:
            return None
        return candidate

    def _learn_shared_work_statement(
        self,
        input_text: str,
        *,
        intent: Intent,
        allow_test_probe: bool = False,
    ) -> dict[str, Any] | None:
        """Persist only clear creator-authored shared project/work milestones.

        Relationship history is the authoritative bounded store for shared
        experiences.  This does not create a second project database and does
        not promote the event into semantic memory automatically.
        """

        intent_name = str(getattr(intent.intent_type, "value", intent.intent_type)).strip().lower()
        if intent_name not in {"conversation", "question", "request", "feedback"}:
            return None

        evidence = self._shared_work_evidence(input_text, allow_test_probe=allow_test_probe)
        if evidence is None:
            return None

        normalized = normalize_for_matching(evidence)
        for event in reversed(self.relationship_history.get_recent(limit=24)):
            if str(event.get("type", "")).strip().lower() != "shared_experience":
                continue
            metadata = event.get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("kind") != "shared_work":
                continue
            if normalize_for_matching(str(event.get("description", ""))) == normalized:
                return {
                    "detected": True,
                    "recorded": False,
                    "already_known": True,
                    "event_id": event.get("id"),
                    "reason": "duplicate_shared_work_event",
                }

        event = self.relationship_history.record_shared_experience(
            evidence,
            importance=0.78,
            metadata={
                "kind": "shared_work",
                "owner": "creator",
                "source": (
                    "production_benchmark_fixture"
                    if allow_test_probe
                    else "creator_natural_shared_work"
                ),
            },
        )
        self.relationship.save()
        return {
            "detected": True,
            "recorded": True,
            "already_known": False,
            "event_id": event.get("id"),
            "source": "relationship_history",
        }

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
        *,
        recent_conversation: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Answer from Mary's local creator model and durable/session memory."""

        query_type = str(
            intent.parameters.get("relationship_query_type", "overview")
        ).strip().lower()
        if query_type == "curiosity_gaps":
            self.relationship_curiosity.sync()
            self.agency.rebuild_priorities()
            response = self.relationship_curiosity.answer_query()
        elif query_type == "memory_overview":
            response = self._creator_memory_overview(
                recent_conversation=recent_conversation or [],
            )
        elif query_type == "shared_work":
            response = self._creator_shared_work_overview(
                recent_conversation=recent_conversation or [],
            )
        elif query_type == "relationship_overview":
            creator_view = self._natural_creator_profile_overview()
            relationship_evidence = self.self_introspection.build("relationship")
            relationship_view = str(
                relationship_evidence.get("fallback_response", "")
            ).strip()
            response = creator_view
            if relationship_view:
                response += " " + relationship_view
        elif query_type in {"overview", "interests", "goals", "values", "preferences"}:
            response = self._natural_creator_profile_overview(query_type=query_type)
        else:
            response = self.relationship.answer_query(query_type)

        return {
            "system_response": response
        }

    def _creator_profile_for_conversation(self) -> dict[str, Any]:
        """Return creator state suitable for normal conversation, not debugging.

        Obvious development/test probes remain in durable state for audit and
        recovery, but they do not become ordinary claims about Unbe.
        """

        evidence_by_id: dict[str, str] = {}
        for memory in self._all_available_memories():
            memory_id = str(getattr(memory, "id", "") or "")
            if memory_id:
                evidence_by_id[memory_id] = self._memory_to_text(memory)
        return conversation_profile(
            self.user_model,
            evidence_by_id=evidence_by_id,
        )

    def _natural_creator_profile_overview(
        self,
        *,
        query_type: str = "overview",
    ) -> str:
        """Render structured creator state as natural Mary-facing prose."""

        creator_name = str(
            self.user_model.name or self.identity.creator or "Unbe"
        ).title()
        profile = self._creator_profile_for_conversation()
        preferences = profile.get("preferences", {}) if isinstance(profile, dict) else {}
        interests = profile.get("interests", []) if isinstance(profile, dict) else []
        goals = profile.get("goals", []) if isinstance(profile, dict) else []
        values = profile.get("values", []) if isinstance(profile, dict) else []
        facts = profile.get("facts", {}) if isinstance(profile, dict) else {}
        communication = profile.get("communication_style", {}) if isinstance(profile, dict) else {}
        general = profile.get("general", []) if isinstance(profile, dict) else []

        query_type = str(query_type or "overview").strip().lower()
        if query_type == "interests":
            return (
                f"The interests you've explicitly shared with me are {', '.join(map(str, interests[:6]))}."
                if interests
                else "I don't have any explicit interests from you stored yet."
            )
        if query_type == "goals":
            return (
                f"The goals you've explicitly shared with me are {', '.join(map(str, goals[:6]))}."
                if goals
                else "I don't have any explicit goals from you stored yet."
            )
        if query_type == "values":
            return (
                f"The values you've explicitly shared with me are {', '.join(map(str, values[:6]))}."
                if values
                else "I don't have any explicit values from you stored yet."
            )
        if query_type == "preferences":
            if not preferences:
                return "I don't have any explicit preferences from you stored yet."
            readable = [
                f"your {str(key).replace('_', ' ')} is {value}"
                for key, value in list(preferences.items())[:6]
            ]
            return "What I currently have is that " + "; ".join(readable) + "."

        pieces = [f"I know {creator_name} is my creator."]
        if goals:
            pieces.append("Your current goals include " + ", ".join(map(str, goals[:4])) + ".")
        if interests:
            pieces.append("You’ve told me you’re interested in " + ", ".join(map(str, interests[:4])) + ".")
        if preferences:
            readable = [
                f"{str(key).replace('_', ' ')}: {value}"
                for key, value in list(preferences.items())[:4]
            ]
            pieces.append("I also have a few explicit preferences from you—" + "; ".join(readable) + ".")
        if values:
            pieces.append("Values you’ve explicitly shared include " + ", ".join(map(str, values[:4])) + ".")
        if facts:
            readable = [
                f"{str(key).replace('_', ' ')}: {value}"
                for key, value in list(facts.items())[:4]
            ]
            pieces.append("A few other stored facts are " + "; ".join(readable) + ".")
        if communication:
            readable = [str(value) for value in list(communication.values())[:3]]
            pieces.append("For how we talk, I have " + ", ".join(readable) + " as your explicit preference.")
        if general:
            pieces.append("You’ve also explicitly shared " + "; ".join(map(str, general[:3])) + ".")
        if len(pieces) == 1:
            pieces.append("I don't have much additional structured creator information stored yet.")
        return " ".join(pieces)

    def _creator_shared_work_overview(
        self,
        *,
        recent_conversation: list[dict[str, str]],
    ) -> str:
        """Recall grounded shared project/work continuity across durable layers."""

        items: list[tuple[int, str, str]] = []
        seen: set[str] = set()

        def add(
            text: Any,
            *,
            source: str,
            score: int,
            creator_owned: bool = False,
            allow_test_probe: bool = False,
        ) -> None:
            value = " ".join(str(text or "").split()).strip()
            if creator_owned:
                value = self._render_creator_owned_shared_work(value)
            if not value or (text_has_test_probe_marker(value) and not allow_test_probe):
                return
            key = normalize_for_matching(value)
            if not key or key in seen:
                return
            seen.add(key)
            items.append((score, value, source))

        # Explicit durable relationship milestones are strongest shared-history
        # evidence because they were intentionally represented as relationship
        # continuity rather than generic creator preferences.
        for milestone in self.relationship_milestones.get_recent(limit=12):
            add(
                milestone.get("description") or milestone.get("title"),
                source="relationship_milestone",
                score=100 + int(float(milestone.get("importance", 0.0) or 0.0) * 10),
            )

        for event in self.relationship_history.get_recent(limit=32):
            event_type = str(event.get("type", "")).strip().lower()
            metadata = event.get("metadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            if event_type == "milestone":
                add(event.get("description"), source="relationship_history", score=96)
            elif event_type == "shared_experience" and metadata.get("kind") == "shared_work":
                add(
                    event.get("description"),
                    source="shared_work_history",
                    score=94,
                    creator_owned=metadata.get("owner") == "creator",
                    allow_test_probe=metadata.get("source") == "production_benchmark_fixture",
                )

        # Current-session evidence keeps a brand-new milestone available before
        # the user restarts Mary.  Only declarative shared-work statements pass.
        for message in recent_conversation:
            if not isinstance(message, dict) or str(message.get("role", "")) != "user":
                continue
            evidence = self._shared_work_evidence(str(message.get("content", "")))
            if evidence:
                add(evidence, source="current_session", score=90, creator_owned=True)

        # Episodic/semantic layers contribute only when explicitly tagged as
        # shared work/project continuity.  This prevents unrelated preferences
        # (for example a preference mentioning "working on projects") from
        # masquerading as shared project history.
        for memory in self._all_available_memories():
            if isinstance(memory, dict):
                metadata = memory.get("metadata", {})
                event_type = str(memory.get("event_type", "")).strip().lower()
            else:
                metadata = getattr(memory, "metadata", {})
                event_type = str(getattr(memory, "event_type", "")).strip().lower()
            metadata = metadata if isinstance(metadata, dict) else {}
            if not (
                metadata.get("shared_work") is True
                or metadata.get("kind") == "shared_work"
                or event_type in {"shared_work", "project", "project_milestone", "shared_experience"}
            ):
                continue
            add(self._memory_to_text(memory), source="memory", score=82)

        items.sort(key=lambda item: item[0], reverse=True)
        selected = items[:6]
        self._last_memory_recall_trace = {
            "query_type": "shared_work",
            "candidate_count": len(items),
            "selected_count": len(selected),
            "sources": sorted({source for _, _, source in selected}),
        }

        if not selected:
            return (
                "I don't have enough grounded shared-work history recorded yet to give you a real project recap. "
                "I can still remember creator facts and preferences, but I won't turn those into project history just because they mention work."
            )

        statements = [text for _, text, _ in selected]
        if len(statements) == 1:
            return (
                "The shared work I can actually ground right now is this: "
                + statements[0]
                + ". I don't have enough older shared-work milestones stored yet to pretend I remember more than that."
            )

        return "What I can actually ground from our shared-work history is: " + "; ".join(statements) + "."

    def _creator_memory_overview(
        self,
        *,
        recent_conversation: list[dict[str, str]],
    ) -> str:
        """Summarize what Mary actually knows/remembers about her creator."""

        creator_name = str(
            self.user_model.name or self.identity.creator or "Unbe"
        ).title()

        profile = self._creator_profile_for_conversation()
        durable_parts: list[str] = []

        preferences = profile.get("preferences", {}) if isinstance(profile, dict) else {}
        interests = profile.get("interests", []) if isinstance(profile, dict) else []
        goals = profile.get("goals", []) if isinstance(profile, dict) else []
        values = profile.get("values", []) if isinstance(profile, dict) else []
        facts = profile.get("facts", {}) if isinstance(profile, dict) else {}
        general = profile.get("general", []) if isinstance(profile, dict) else []

        if preferences:
            rendered = ", ".join(
                f"{str(key).replace('_', ' ')} = {value}"
                for key, value in list(preferences.items())[:5]
            )
            durable_parts.append("preferences: " + rendered)
        if interests:
            durable_parts.append("interests: " + ", ".join(map(str, interests[:5])))
        if goals:
            durable_parts.append("goals: " + ", ".join(map(str, goals[:5])))
        if values:
            durable_parts.append("values: " + ", ".join(map(str, values[:5])))
        if facts:
            rendered = ", ".join(
                f"{str(key).replace('_', ' ')} = {value}"
                for key, value in list(facts.items())[:5]
            )
            durable_parts.append("facts: " + rendered)
        if general:
            durable_parts.append("other: " + "; ".join(map(str, general[:4])))

        creator_memories: list[str] = []
        for memory in reversed(self._all_available_memories()):
            if not self._memory_is_creator_owned(memory):
                continue
            text = self._memory_to_text(memory)
            if text_has_test_probe_marker(text):
                continue
            if text and text not in creator_memories:
                creator_memories.append(text)
            if len(creator_memories) >= 4:
                break

        session_shares: list[str] = []
        for item in reversed(recent_conversation):
            if not isinstance(item, dict) or str(item.get("role", "")) != "user":
                continue
            text = " ".join(str(item.get("content", "")).split())
            if not text or text.lower() in {"approve", "reject"}:
                continue
            # Prefer statements the creator volunteered over benchmark-like questions.
            if text.rstrip().endswith("?"):
                continue
            if len(text.split()) < 4:
                continue
            if len(text) > 180:
                text = text[:179].rstrip() + "…"
            if text not in session_shares:
                session_shares.append(text)
            if len(session_shares) >= 3:
                break
        session_shares.reverse()

        pieces = [f"Yeah. I remember that {creator_name} is my creator."]
        natural_profile = self._natural_creator_profile_overview()
        # Avoid repeating the creator sentence when composing the memory answer.
        prefix = f"I know {creator_name} is my creator. "
        if natural_profile.startswith(prefix):
            natural_profile = natural_profile[len(prefix):]
        if natural_profile:
            pieces.append(natural_profile)
        elif creator_memories:
            pieces.append("I also have durable creator-owned memories, including " + "; ".join(creator_memories) + ".")
        else:
            pieces.append("I don't currently have many additional durable creator facts stored yet.")

        if creator_memories:
            pieces.append("A few durable memories I can actually retrieve are " + "; ".join(creator_memories) + ".")
        if session_shares:
            pieces.append("And from this current session I remember you saying " + "; ".join(session_shares) + ".")

        return " ".join(pieces)

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

    def _sync_creator_directives_to_agency(self) -> None:
        """Reconcile durable creator directives into derived agency state.

        Creator directives are authoritative for creator-directed internal
        orientation. Curiosity/priority entries are derived runtime state.
        If derived files are missing, stale, or were restored from an older
        checkpoint, Mary rebuilds the active creator curiosity from the
        directive rather than silently forgetting it.
        """

        creator_name = str(
            self.user_model.name or self.identity.creator or "Unbe"
        ).strip() or "Unbe"
        description = f"Learn more about {creator_name.title()}"
        changed = False

        for directive in self.creator_directives.get_active():
            if str(directive.get("category", "")).strip().lower() != "relationship_curiosity":
                continue

            target = str(directive.get("target", "")).strip().lower()
            if target not in {"unbe", "creator", "creator_relationship"}:
                continue

            metadata = directive.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            top_priority = bool(metadata.get("top_priority", False))
            try:
                directive_priority = float(directive.get("priority", 0.9))
            except (TypeError, ValueError):
                directive_priority = 0.9
            directive_priority = max(0.0, min(1.0, directive_priority))

            desired_importance = 1.0 if top_priority else directive_priority
            desired_urgency = 1.0 if top_priority else 0.5

            existing = None
            for curiosity in self.agency.curiosities.get_curiosities():
                if curiosity.get("status") not in {"open", "exploring"}:
                    continue
                if str(curiosity.get("description", "")).strip().lower() != description.lower():
                    continue
                if not bool(curiosity.get("creator_directed")) and curiosity.get("source") != "creator_directive":
                    continue
                existing = curiosity
                break

            if existing is None:
                existing = self.agency.curiosities.add_curiosity(
                    description=description,
                    importance=desired_importance,
                    source="creator_directive",
                    metadata={
                        "directive_id": directive.get("id"),
                        "creator_directed": True,
                        "top_priority": top_priority,
                    },
                )
                changed = existing is not None or changed

            if existing is None:
                continue

            before = (
                existing.get("importance"),
                existing.get("urgency"),
                existing.get("relevance"),
                existing.get("directive_id"),
                existing.get("creator_directed"),
                existing.get("source"),
            )
            existing["importance"] = desired_importance
            existing["urgency"] = desired_urgency
            existing["relevance"] = 1.0
            existing["directive_id"] = directive.get("id")
            existing["creator_directed"] = True
            existing["source"] = "creator_directive"
            existing_metadata = existing.get("metadata")
            existing_metadata = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
            existing_metadata.update({
                "directive_id": directive.get("id"),
                "creator_directed": True,
                "top_priority": top_priority,
            })
            existing["metadata"] = existing_metadata
            after = (
                existing.get("importance"),
                existing.get("urgency"),
                existing.get("relevance"),
                existing.get("directive_id"),
                existing.get("creator_directed"),
                existing.get("source"),
            )
            if before != after:
                changed = True

        if changed:
            self.agency.curiosities.save()

        self.agency.rebuild_priorities()

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

        existing_directive = self.creator_directives.find_active(
            category="relationship_curiosity",
            target=target,
        )
        if existing_directive is not None:
            existing_priority = float(
                existing_directive.get("priority", 0.0)
            )
            existing_top_priority = bool(
                (existing_directive.get("metadata") or {}).get(
                    "top_priority",
                    False,
                )
            )
            priority = max(priority, existing_priority)
            top_priority = top_priority or existing_top_priority

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
        *,
        incoming_emotion_appraisal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Provide grounded local evidence for questions about Mary herself."""

        subtype = str(
            intent.parameters.get(
                "self_query_type",
                "identity",
            )
        ).strip().lower()

        if subtype == "runtime_architecture":
            return {
                "system_response": self._runtime_architecture_response(
                    query=str(
                        intent.parameters.get(
                            "query",
                            "",
                        )
                    )
                ),
                "skip_cognition": True,
            }

        if subtype == "development":
            evidence = self._self_development_evidence(
                query=str(intent.parameters.get("query", ""))
            )
        else:
            evidence = self.self_introspection.build(
                subtype,
                query=str(
                    intent.parameters.get(
                        "query",
                        "",
                    )
                ),
            )

        if subtype == "relationship_feelings" and incoming_emotion_appraisal:
            evidence["incoming_turn_appraisal"] = dict(incoming_emotion_appraisal)
            prompt_evidence = evidence.get("prompt_evidence")
            if isinstance(prompt_evidence, dict):
                prompt_evidence["incoming_turn_appraisal"] = {
                    key: incoming_emotion_appraisal.get(key)
                    for key in ("emotion", "intensity", "relationship_relevance", "source")
                    if incoming_emotion_appraisal.get(key) not in (None, "")
                }

        # Dynamic agency state is runtime truth, not a prose-generation task.
        # Current priorities and current curiosities are therefore answered
        # locally and deterministically so a language model cannot invent items
        # that are not represented in Mary's actual agency state.
        if subtype in {"priorities", "curiosity"}:
            return {
                "system_response": str(
                    evidence.get("fallback_response", "")
                ).strip(),
                "skip_cognition": True,
            }

        return {
            "knowledge": [evidence],
        }

    def _self_development_evidence(
        self,
        *,
        query: str = "",
    ) -> dict[str, Any]:
        """Ground ``have you changed?`` in represented Mary state.

        Stable canon, developed-self state, relationship learning, and current
        capabilities are kept distinct. This does not claim every architecture
        upgrade changed Mary's personality; it gives the language layer evidence
        for describing what actually became richer over time.
        """

        base = self.self_introspection.build("self_understanding", query=query)
        personality_summary = self.personality_development_summary()
        personality_history = list(getattr(self.personality_development, "history", []) or [])[-5:]
        developed_status = dict(self.developed_self_state.status() or {})
        preference_summary = dict(self.preference_promotion_summary() or {})
        creator_profile = self._creator_profile_for_conversation()

        creator_counts = {
            "preferences": len(creator_profile.get("preferences", {}) or {}),
            "interests": len(creator_profile.get("interests", []) or []),
            "goals": len(creator_profile.get("goals", []) or []),
            "values": len(creator_profile.get("values", []) or []),
            "facts": len(creator_profile.get("facts", {}) or {}),
            "communication": len(creator_profile.get("communication_style", {}) or {}),
        }
        learned_creator_items = sum(creator_counts.values())

        current_capabilities = {
            "conversation_route": list(self.llm.conversation_provider_order())
            if callable(getattr(self.llm, "conversation_provider_order", None))
            else [],
            "task_route": list(self.llm._provider_order(None))
            if callable(getattr(self.llm, "_provider_order", None))
            else [],
            "system_contract": getattr(self.system_contract, "VERSION", None),
            "memory_persistent_capable": bool(self.status().get("memory", {}).get("connected", True)),
        }

        if personality_history:
            personality_phrase = (
                f"I have {len(personality_history)} recent represented personality-development record(s) in the loaded history."
            )
        else:
            personality_phrase = (
                "I don't have a represented personality-development event to claim from the loaded development history."
            )

        relationship_phrase = (
            f"My structured creator model currently has {learned_creator_items} non-probe item(s) across preferences, interests, goals, values, facts, and communication."
            if learned_creator_items
            else "My structured creator model does not currently contain a non-probe item to use as evidence of relationship learning."
        )

        fallback = (
            "My core authored character is still Mary; I shouldn't pretend a model response rewrote that. "
            + personality_phrase + " " + relationship_phrase + " "
            "What has clearly changed at the system level is how much continuity, relationship context, emotional appraisal, routing, tools, and self-grounding I can bring into a turn. "
            "So the grounded answer can be: my canon may be stable while the represented version of me interacting with you has become more informed and capable."
        )

        compact = {
            "core_character_policy": "authored canon stays stable unless an explicit creator/development path changes it",
            "personality_development": {
                "summary": personality_summary,
                "recent_history": personality_history,
            },
            "developed_self": developed_status,
            "preference_development": preference_summary,
            "relationship_learning_counts": creator_counts,
            "current_capabilities": current_capabilities,
            "interpretation": (
                "Distinguish stable authored Mary from controlled developed-self changes, relationship learning, and capability/runtime growth. "
                "Do not claim a personality change without represented development evidence."
            ),
        }

        base.update({
            "subtype": "development",
            "self_development": compact,
            "fallback_response": fallback,
            "prompt_evidence": {
                "subtype": "development",
                "self_development": compact,
                "fallback_response": fallback,
            },
        })
        return base

    def _runtime_architecture_response(
        self,
        *,
        query: str = "",
    ) -> str:
        """Answer runtime/host/provider questions from authoritative state.

        Breakthrough 12.2 intentionally keeps these answers question-shaped:
        provider questions receive provider state, host questions receive host
        state, and only broad architecture questions receive the full system
        explanation. No language model or web lookup is used.
        """

        cognition_status = dict(self.status().get("cognition", {}) or {})
        strategy = str(cognition_status.get("routing_strategy", "configured"))
        provider_order = [
            str(item)
            for item in cognition_status.get("provider_order", [])
            if str(item).strip()
        ]
        conversation_order = [
            str(item)
            for item in cognition_status.get("conversation_provider_order", [])
            if str(item).strip()
        ]
        environment = self.runtime_environment.snapshot()
        override = (
            self.llm.session_override_status()
            if callable(getattr(self.llm, "session_override_status", None))
            else {"provider": None, "route": None}
        )

        return self.runtime_introspection.render(
            query=query,
            environment=environment,
            routing_strategy=strategy,
            configured_task_route=provider_order,
            configured_conversation_route=conversation_order,
            session_override=override,
            last_generation=dict(self._last_generation_metadata or {}),
        )

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
            conversation=list(
                context.get("conversation", [])
            ),
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
            mind_state=dict(
                context.get("mind_state", {})
            ),
        )

        reasoning_metadata: dict[str, Any] = {
            "llm_skipped": True,
            "self_grounded": bool(
                intent is not None
                and intent.intent_type == IntentType.SELF_QUERY
            ),
        }
        if (
            intent is not None
            and intent.intent_type == IntentType.SELF_QUERY
            and str(intent.parameters.get("self_query_type", "")).strip().lower()
            == "runtime_architecture"
        ):
            reasoning_metadata.update({
                "provider": "local/system",
                "model": "n/a",
                "generation_purpose": "runtime_introspection",
                "turn_policy": {
                    "category": "local_runtime",
                    "generation_purpose": "runtime_introspection",
                    "local_first": False,
                    "rationale": "runtime facts come from Mary's process-local environment state",
                },
            })

        reasoning = ReasoningResult(
            response=response,
            confidence=1.0,
            reasoning_type="deterministic_system_action",
            intent=intent,
            metadata=reasoning_metadata,
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

    def _handle_llm_control(
        self,
        intent: Intent,
        *,
        original_input: str,
    ) -> dict[str, Any]:
        """Apply explicit process-local model routing or one-task expert use.

        This path never roleplays a provider action. A route-change response is
        returned only after the router state changes. Paid OpenAI remains bounded
        to an explicitly authorized ephemeral task.
        """

        operation = str(intent.parameters.get("operation", "")).strip().lower()

        if operation == "clear_session":
            status = self.llm.clear_session_override()
            return {
                "system_response": (
                    "Okay. I cleared the temporary model override. My normal routing policy is active again: "
                    "ordinary personal conversation is local-first ("
                    + " -> ".join(
                        self.llm.conversation_provider_order()
                        if callable(getattr(self.llm, "conversation_provider_order", None))
                        else self.llm._provider_order(None)
                    )
                    + "), while task/general generation uses free-first ("
                    + " -> ".join(self.llm._provider_order(None))
                    + ")."
                ),
                "skip_cognition": True,
                "llm_control": status,
            }

        if operation == "set_session":
            provider = intent.parameters.get("provider")
            route = intent.parameters.get("route")
            requested = str(intent.parameters.get("requested_provider") or provider or route or "").strip()
            try:
                status = self.llm.set_session_override(
                    provider=(str(provider).strip() if provider else None),
                    route=(str(route).strip() if route else None),
                )
            except Exception as exc:
                return {
                    "system_response": f"I couldn't change the model route: {type(exc).__name__}: {exc}",
                    "skip_cognition": True,
                }

            if status.get("route") == "private":
                response = (
                    "Okay. Local-only generation is active for this process now. "
                    "My ordinary model-backed turns will route through Ollama until you tell me "
                    "to return to the normal/free-first route. Use /last after a generated turn "
                    "to verify the provider that actually answered."
                )
            else:
                response = (
                    f"Okay. I'm temporarily routing ordinary model-backed turns through {requested}. "
                    "Use /last after a generated turn to verify what actually answered. "
                    "Tell me to use the normal/free-first route when you want to clear it."
                )
            return {
                "system_response": response,
                "skip_cognition": True,
                "llm_control": status,
            }

        if operation == "paid_expert_once":
            if not bool(intent.parameters.get("paid_authorized", False)):
                return {
                    "system_response": (
                        "OpenAI is my paid expert route, so I won't call it from an ambiguous request. "
                        "If you want one paid consultation for this task, explicitly tell me to use/call OpenAI."
                    ),
                    "skip_cognition": True,
                }

            task = self.task_workspace.create_task(
                original_input,
                metadata={
                    "allow_paid": True,
                    "needs_expert": True,
                    "source": "creator_explicit_provider_request",
                },
            )
            try:
                plan = self.task_orchestrator.plan(
                    task.task_id,
                    allow_paid=True,
                    needs_expert=True,
                )
                execution = self.task_executor.execute(
                    plan,
                    prompt=str(intent.parameters.get("query") or original_input),
                )
            except Exception as exc:
                self.task_workspace.fail(task.task_id, outcome=f"{type(exc).__name__}: {exc}")
                return {
                    "system_response": f"The OpenAI expert call failed: {type(exc).__name__}: {exc}",
                    "skip_cognition": True,
                }

            if not execution.success:
                self.task_workspace.fail(task.task_id, outcome=execution.content)
                return {
                    "system_response": (
                        "I did not complete the OpenAI expert call. "
                        f"Status: {execution.status}. {execution.content}"
                    ),
                    "skip_cognition": True,
                }

            self.task_workspace.complete(
                task.task_id,
                outcome=f"Expert consultation completed via {execution.source}/{execution.model}.",
            )
            return {
                "knowledge": [
                    {
                        "expert_consultation": True,
                        "task_local": True,
                        "advisory_only": True,
                        "provider": execution.source,
                        "model": execution.model,
                        "content": execution.content,
                        "usage": dict(execution.usage),
                    }
                ],
                "sources": [],
                "skip_cognition": False,
            }

        return {
            "system_response": "I couldn't determine the requested model-routing action.",
            "skip_cognition": True,
        }

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

            learning_outcome = self.knowledge_learning.ingest_evaluation(
                subject=query,
                statement=statement,
                source=source,
                evaluation=evaluation,
                category="research",
            )

            if learning_outcome.promoted:
                try:
                    # Reservoir/vector state is derived. Mark it dirty so the
                    # newly trusted knowledge is indexed during maintenance
                    # without blocking the active response path.
                    self.mind.reservoir_dirty = True
                except Exception:
                    pass

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
                    "learning": learning_outcome.to_dict(),
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

        # 13.1.1 memory-integrity guard.
        # Repair the known legacy boundary-collapse artifact at the final
        # canonical write boundary so it can never persist again.
        content = re.sub(
            r"\bmemoryto\b",
            "memory to",
            content,
            flags=re.IGNORECASE,
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

        has_creator_first_person = bool(
            re.search(
                r"\b(?:i|i'm|i've|i'll|i'd|me|my|mine|myself)\b",
                content,
                flags=re.IGNORECASE,
            )
        )
        has_second_person = bool(
            re.search(
                r"\b(?:you|you're|you've|you'll|you'd|your|yours|yourself)\b",
                content,
                flags=re.IGNORECASE,
            )
        )

        if has_creator_first_person and has_second_person:
            return "Got it. I'll remember this."

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
        semantic = list(
            self.memory.semantic.all()
        )

        # Episodic and semantic memory are complementary layers.  Higher-level
        # recall must not hide semantic memory merely because at least one
        # episodic record exists.
        return episodic + semantic

    def memory_lifecycle_status(self) -> dict[str, Any]:
        """Return display-safe memory/relationship lifecycle observability."""

        status = self.memory.status()
        lifecycle = self.memory.lifecycle_status()
        shared_events = 0
        for event in self.relationship_history.get_all():
            metadata = event.get("metadata", {}) if isinstance(event, dict) else {}
            if (
                isinstance(event, dict)
                and event.get("type") == "shared_experience"
                and isinstance(metadata, dict)
                and metadata.get("kind") == "shared_work"
            ):
                shared_events += 1
        return {
            "counts": dict(status.get("counts", {}) or {}),
            "capacities": dict(status.get("capacities", {}) or {}),
            "last_memory_event": dict(lifecycle.get("last_event", {}) or {}),
            "consolidation": dict(lifecycle.get("consolidation", {}) or {}),
            "shared_work": {
                "durable_events": shared_events,
                "last_learning": dict(self._last_shared_work_learning),
                "last_recall": dict(getattr(self, "_last_memory_recall_trace", {}) or {}),
            },
        }

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
            "preferences": {
                "count": len(self.preferences.get_preferences()),
                "likes": len(self.preferences.get_likes()),
                "dislikes": len(self.preferences.get_dislikes()),
            },
            "developed_self": self.developed_self_state.status(),
            "user": self._user_context(),
            "learning": self.learner.summarize(),
            "memory": self.memory.status(),
            "relationship_governance": self.relationship.governance_status(),
            "governance": {
                "limits": self.config.governance.to_dict(),
                "resources": (
                    self.llm.resource_governor.status()
                    if hasattr(self.llm, "resource_governor")
                    else {"policy": "external_test_router"}
                ),
                "principle": "bounded_growth_no_unlimited_collection",
            },
            "architecture_contract": self.system_contract.snapshot(self),
            "runtime_environment": self.runtime_environment.snapshot(),
            "conversation_learning": self.conversation_learning.status(),
            "turn_policy": self.turn_policy.status(),
            "orchestration": {
                "task_workspace": self.task_workspace.status(),
                "expert_consultant": self.expert_consultant.status(),
                "task_orchestrator": self.task_orchestrator.status(),
                "task_executor": self.task_executor.status(),
            },
            "tools": self.tools.status(),
            "live_character": self.live_state(),
            "cognition": {
                "reasoning": True,
                "reflection": True,
                "turn_mind": True,
                "context_lifecycle": True,
                "llm": self.llm.provider_name(),
                "model": self.llm.model_name(),
                "routing_strategy": (
                    self.llm.routing_strategy()
                    if callable(getattr(self.llm, "routing_strategy", None))
                    else "configured"
                ),
                "provider_order": (
                    self.llm._provider_order(None)
                    if callable(getattr(self.llm, "_provider_order", None))
                    else [self.llm.provider_name()]
                ),
                "conversation_provider_order": (
                    self.llm.conversation_provider_order()
                    if callable(getattr(self.llm, "conversation_provider_order", None))
                    else (
                        self.llm._provider_order(None)
                        if callable(getattr(self.llm, "_provider_order", None))
                        else [self.llm.provider_name()]
                    )
                ),
                "session_override": (
                    self.llm.session_override_status()
                    if callable(getattr(self.llm, "session_override_status", None))
                    else {"provider": None, "route": None}
                ),
            },
        }

    def live_state(self, *, runtime_status: str | None = None) -> dict[str, Any]:
        """Return a compact display-safe live character/runtime snapshot."""

        from mary.runtime.live_state import build_live_character_state

        return build_live_character_state(self, runtime_status=runtime_status)

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

    def _user_context_for_model(self) -> dict[str, Any]:
        """Return a provenance-safe creator projection for model-backed turns.

        Durable test/probe records remain in RelationshipManager and `/audit`,
        but normal generation and reflection never receive them as conversational
        facts.
        """

        try:
            profile = conversation_profile(self.user_model)
        except Exception:
            return {}

        identity = profile.get("identity", {})
        identity = identity if isinstance(identity, dict) else {}
        return {
            "creator_id": identity.get("id", getattr(self.user_model, "creator_id", "creator")),
            "name": identity.get("name", getattr(self.user_model, "name", "Unbe")),
            "facts": dict(profile.get("facts", {}) or {}),
            "preferences": dict(profile.get("preferences", {}) or {}),
            "interests": list(profile.get("interests", []) or []),
            "values": list(profile.get("values", []) or []),
            "goals": list(profile.get("goals", []) or []),
            "communication_style": dict(profile.get("communication_style", {}) or {}),
            "general": list(profile.get("general", []) or []),
        }

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

    def _wire_personality_development(self) -> None:
        """Wire development to Mary's authoritative live self objects."""

        bindings = {
            "personality": self.personality,
            "values": self.values,
            "preferences": self.preferences,
        }

        for name, value in bindings.items():
            try:
                setattr(self.personality_development, name, value)
            except (AttributeError, TypeError):
                # PersonalityDevelopment historically required only personality.
                # Older implementations can still run while newer ones receive
                # the richer live bindings when those attributes are supported.
                continue

    def configure_developed_self_persistence(
        self,
        path: str | Any,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        """Enable durable developed-self persistence for this Mary instance."""

        self._wire_personality_development()
        self.developed_self_state.rebind(
            personality=self.personality,
            values=self.values,
            preferences=self.preferences,
            personality_development=self.personality_development,
        )
        loaded = self.developed_self_state.configure(
            path,
            auto_save=auto_save,
            load=load,
        )
        self._wire_personality_development()
        return loaded

    def save_developed_self_state(self) -> bool:
        """Persist developed state when the persistent runtime configured it."""

        return self.developed_self_state.save()

    def configure_preference_promotion_persistence(
        self,
        path: str | Any,
        *,
        auto_save: bool = True,
        load: bool = True,
    ) -> bool:
        """Enable persistence for tentative preference-development evidence."""

        return self.preference_promotion.configure(
            path,
            auto_save=auto_save,
            load=load,
        )

    def save_preference_promotion_state(self) -> bool:
        """Persist tentative preference evidence when configured."""

        return self.preference_promotion.save()

    def observe_preference_experience(
        self,
        name: str,
        *,
        category: str = "general",
        strength: float = 0.5,
        polarity: float = 1.0,
        confidence: float = 0.5,
        source: str = "experience",
        reason: str = "",
        evidence_id: str | None = None,
    ) -> dict[str, Any]:
        """Record tentative non-model evidence without changing Mary's self."""

        return self.preference_promotion.observe(
            name,
            category=category,
            strength=strength,
            polarity=polarity,
            confidence=confidence,
            source=source,
            reason=reason,
            evidence_id=evidence_id,
        )

    def evaluate_preference_candidate(
        self,
        name: str,
    ) -> dict[str, Any]:
        """Return deterministic promotion eligibility for a candidate."""

        return self.preference_promotion.evaluate(name)

    def promote_preference_candidate(
        self,
        name: str,
    ) -> dict[str, Any]:
        """Explicitly promote an eligible candidate into developed self-state."""

        spec = self.preference_promotion.promotion_spec(name)
        evaluation = self.preference_promotion.evaluate(name)

        if spec is None:
            return {
                "promoted": False,
                "reason": evaluation.get(
                    "reason",
                    "Preference candidate is not eligible.",
                ),
                "evaluation": evaluation,
            }

        existing = self.preferences.get_preference(spec["name"])
        if isinstance(existing, dict):
            existing_source = str(existing.get("source", "")).strip().lower()
            if existing_source in {
                "character_core",
                "canonical",
                "authored",
                "authored_preferences",
            }:
                return {
                    "promoted": False,
                    "reason": (
                        "Canonical authored preferences cannot be overwritten "
                        "through experience promotion."
                    ),
                    "evaluation": evaluation,
                }

        preference = self.set_developed_preference(**spec)
        self.preference_promotion.mark_promoted(
            spec["name"],
            preference=preference,
        )

        return {
            "promoted": True,
            "preference": preference,
            "evaluation": evaluation,
        }

    def reject_preference_candidate(
        self,
        name: str,
        *,
        reason: str = "",
    ) -> bool:
        """Explicitly reject tentative evidence without changing Preferences."""

        return self.preference_promotion.reject(
            name,
            reason=reason,
        )

    def preference_promotion_summary(self) -> dict[str, Any]:
        """Return compact tentative preference-development state."""

        return self.preference_promotion.summary()

    def set_developed_preference(
        self,
        name: str,
        *,
        category: str = "general",
        strength: float = 0.5,
        polarity: float = 1.0,
        confidence: float = 0.5,
        source: str = "experience",
    ) -> dict[str, Any]:
        """Create/update a durable preference through an explicit self path."""

        normalized_source = str(source).strip().lower() or "experience"
        if normalized_source in {
            "model",
            "model_dialogue",
            "llm",
            "llm_output",
            "situational",
            "imagination",
        }:
            raise ValueError(
                "Model/situational output cannot be a durable preference source."
            )

        preference = self.preferences.set_preference(
            name=name,
            category=category,
            strength=strength,
            polarity=polarity,
            confidence=confidence,
            source=normalized_source,
        )
        self.developed_self_state.save_if_configured()
        return preference

    def adjust_developed_preference(
        self,
        name: str,
        amount: float,
        *,
        confidence: float | None = None,
        source: str = "experience",
    ) -> dict[str, Any] | None:
        """Adjust a durable preference through the experience path."""

        normalized_source = str(source).strip().lower() or "experience"
        if normalized_source in {
            "model",
            "model_dialogue",
            "llm",
            "llm_output",
            "situational",
            "imagination",
        }:
            raise ValueError(
                "Model/situational output cannot be a durable preference source."
            )

        preference = self.preferences.adjust(
            name=name,
            amount=amount,
            confidence=confidence,
            source=normalized_source,
        )
        self.developed_self_state.save_if_configured()
        return preference

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

        applied = self.personality_development.apply(
            proposal,
        )

        if applied:
            self.developed_self_state.record_approved_personality_change(
                proposal
            )

        return bool(applied)

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