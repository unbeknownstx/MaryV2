"""MaryV2 bounded-runtime limits.

A persistent character must be allowed to grow without allowing any individual
collection, prompt, task, provider route, or backup chain to grow forever.
These limits are infrastructure policy; they do not define Mary's character.

Defaults are deliberately generous for a private single-user V2 runtime while
remaining small enough for years of ordinary use on a normal PC. Every value
can be overridden with an environment variable without changing code.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = int(default)
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = int(default)
    value = max(int(minimum), value)
    if maximum is not None:
        value = min(int(maximum), value)
    return value


@dataclass(frozen=True)
class RuntimeLimits:
    """Central hard/soft resource ceilings for MaryV2."""

    # LLM-facing active context.
    context_turns: int = 4
    context_characters: int = 5_000
    context_message_characters: int = 1_800
    context_anchors: int = 3

    # Durable and working memory.
    working_memory_capacity: int = 50
    memory_recall_limit: int = 8
    memory_context_working_limit: int = 12
    episodic_capacity: int = 4_096
    semantic_capacity: int = 4_096
    memory_content_characters: int = 4_000

    # Relationship state. Current structured facts are favored over historical
    # observations when a collection must be compacted.
    relationship_event_capacity: int = 2_048
    relationship_profile_capacity: int = 2_048
    relationship_observation_capacity: int = 2_048
    relationship_inference_capacity: int = 512
    relationship_pattern_capacity: int = 512
    relationship_milestone_capacity: int = 512
    relationship_text_characters: int = 2_000

    # Persistent agency/directive ledgers. Active/current records are favored.
    goal_capacity: int = 512
    intention_capacity: int = 512
    curiosity_capacity: int = 1_024
    creator_directive_capacity: int = 512
    agency_text_characters: int = 2_000

    # Ephemeral task workspace. These objects intentionally do not survive a
    # process restart, so keeping only a recent working set is sufficient.
    task_capacity: int = 128
    task_evidence_capacity: int = 64
    task_hypothesis_capacity: int = 32
    task_question_capacity: int = 32
    task_action_capacity: int = 64
    task_consultation_capacity: int = 16
    task_decision_capacity: int = 32
    task_text_characters: int = 4_000

    # Process-local learning/research ledgers. These are working histories, not
    # a second durable memory system; compact old entries aggressively.
    learning_event_capacity: int = 512
    evaluation_capacity: int = 512
    research_request_capacity: int = 256
    research_result_capacity: int = 256
    knowledge_candidate_capacity: int = 512
    knowledge_concept_capacity: int = 4_096
    knowledge_source_capacity: int = 2_048
    experiment_capacity: int = 256
    experiment_observation_capacity: int = 64
    process_text_characters: int = 4_000

    # Metadata itself is bounded so a single nested payload cannot bypass the
    # collection ceilings above.
    metadata_item_capacity: int = 64
    metadata_depth: int = 4

    # Provider / paid-resource governance.
    provider_attempts_per_generation: int = 4
    paid_calls_per_task: int = 1
    expert_max_output_tokens: int = 1_200

    # Persistence / recovery.
    backup_generations: int = 3
    state_file_soft_limit_bytes: int = 32 * 1024 * 1024

    # Session/UI runtime.
    dialogue_history_capacity: int = 50

    @classmethod
    def from_environment(cls) -> "RuntimeLimits":
        """Create limits from environment overrides with safe clamping."""

        defaults = cls()
        return cls(
            context_turns=_env_int("MARY_CONTEXT_MAX_TURNS", defaults.context_turns, maximum=32),
            context_characters=_env_int("MARY_CONTEXT_MAX_CHARACTERS", defaults.context_characters, minimum=500, maximum=100_000),
            context_message_characters=_env_int("MARY_CONTEXT_MAX_MESSAGE_CHARACTERS", defaults.context_message_characters, minimum=200, maximum=50_000),
            context_anchors=_env_int("MARY_CONTEXT_MAX_ANCHORS", defaults.context_anchors, minimum=0, maximum=32),
            working_memory_capacity=_env_int("MARY_WORKING_MEMORY_CAPACITY", defaults.working_memory_capacity, maximum=1_000),
            memory_recall_limit=_env_int("MARY_MEMORY_RECALL_LIMIT", defaults.memory_recall_limit, maximum=64),
            memory_context_working_limit=_env_int("MARY_MEMORY_CONTEXT_WORKING_LIMIT", defaults.memory_context_working_limit, maximum=128),
            episodic_capacity=_env_int("MARY_EPISODIC_MEMORY_CAPACITY", defaults.episodic_capacity, maximum=100_000),
            semantic_capacity=_env_int("MARY_SEMANTIC_MEMORY_CAPACITY", defaults.semantic_capacity, maximum=100_000),
            memory_content_characters=_env_int("MARY_MEMORY_MAX_CONTENT_CHARACTERS", defaults.memory_content_characters, minimum=256, maximum=100_000),
            relationship_event_capacity=_env_int("MARY_RELATIONSHIP_EVENT_CAPACITY", defaults.relationship_event_capacity, maximum=50_000),
            relationship_profile_capacity=_env_int("MARY_RELATIONSHIP_PROFILE_CAPACITY", defaults.relationship_profile_capacity, maximum=50_000),
            relationship_observation_capacity=_env_int("MARY_RELATIONSHIP_OBSERVATION_CAPACITY", defaults.relationship_observation_capacity, maximum=50_000),
            relationship_inference_capacity=_env_int("MARY_RELATIONSHIP_INFERENCE_CAPACITY", defaults.relationship_inference_capacity, maximum=20_000),
            relationship_pattern_capacity=_env_int("MARY_RELATIONSHIP_PATTERN_CAPACITY", defaults.relationship_pattern_capacity, maximum=20_000),
            relationship_milestone_capacity=_env_int("MARY_RELATIONSHIP_MILESTONE_CAPACITY", defaults.relationship_milestone_capacity, maximum=20_000),
            relationship_text_characters=_env_int("MARY_RELATIONSHIP_MAX_TEXT_CHARACTERS", defaults.relationship_text_characters, minimum=256, maximum=50_000),
            goal_capacity=_env_int("MARY_GOAL_CAPACITY", defaults.goal_capacity, maximum=10_000),
            intention_capacity=_env_int("MARY_INTENTION_CAPACITY", defaults.intention_capacity, maximum=10_000),
            curiosity_capacity=_env_int("MARY_CURIOSITY_CAPACITY", defaults.curiosity_capacity, maximum=20_000),
            creator_directive_capacity=_env_int("MARY_CREATOR_DIRECTIVE_CAPACITY", defaults.creator_directive_capacity, maximum=10_000),
            agency_text_characters=_env_int("MARY_AGENCY_MAX_TEXT_CHARACTERS", defaults.agency_text_characters, minimum=256, maximum=50_000),
            task_capacity=_env_int("MARY_TASK_CAPACITY", defaults.task_capacity, maximum=5_000),
            task_evidence_capacity=_env_int("MARY_TASK_EVIDENCE_CAPACITY", defaults.task_evidence_capacity, maximum=1_000),
            task_hypothesis_capacity=_env_int("MARY_TASK_HYPOTHESIS_CAPACITY", defaults.task_hypothesis_capacity, maximum=1_000),
            task_question_capacity=_env_int("MARY_TASK_QUESTION_CAPACITY", defaults.task_question_capacity, maximum=1_000),
            task_action_capacity=_env_int("MARY_TASK_ACTION_CAPACITY", defaults.task_action_capacity, maximum=2_000),
            task_consultation_capacity=_env_int("MARY_TASK_CONSULTATION_CAPACITY", defaults.task_consultation_capacity, maximum=256),
            task_decision_capacity=_env_int("MARY_TASK_DECISION_CAPACITY", defaults.task_decision_capacity, maximum=1_000),
            task_text_characters=_env_int("MARY_TASK_MAX_TEXT_CHARACTERS", defaults.task_text_characters, minimum=256, maximum=100_000),
            learning_event_capacity=_env_int("MARY_LEARNING_EVENT_CAPACITY", defaults.learning_event_capacity, maximum=20_000),
            evaluation_capacity=_env_int("MARY_EVALUATION_CAPACITY", defaults.evaluation_capacity, maximum=20_000),
            research_request_capacity=_env_int("MARY_RESEARCH_REQUEST_CAPACITY", defaults.research_request_capacity, maximum=10_000),
            research_result_capacity=_env_int("MARY_RESEARCH_RESULT_CAPACITY", defaults.research_result_capacity, maximum=10_000),
            knowledge_candidate_capacity=_env_int("MARY_KNOWLEDGE_CANDIDATE_CAPACITY", defaults.knowledge_candidate_capacity, maximum=20_000),
            knowledge_concept_capacity=_env_int("MARY_KNOWLEDGE_CONCEPT_CAPACITY", defaults.knowledge_concept_capacity, maximum=100_000),
            knowledge_source_capacity=_env_int("MARY_KNOWLEDGE_SOURCE_CAPACITY", defaults.knowledge_source_capacity, maximum=50_000),
            experiment_capacity=_env_int("MARY_EXPERIMENT_CAPACITY", defaults.experiment_capacity, maximum=10_000),
            experiment_observation_capacity=_env_int("MARY_EXPERIMENT_OBSERVATION_CAPACITY", defaults.experiment_observation_capacity, maximum=1_000),
            process_text_characters=_env_int("MARY_PROCESS_MAX_TEXT_CHARACTERS", defaults.process_text_characters, minimum=256, maximum=100_000),
            metadata_item_capacity=_env_int("MARY_METADATA_ITEM_CAPACITY", defaults.metadata_item_capacity, maximum=1_000),
            metadata_depth=_env_int("MARY_METADATA_DEPTH", defaults.metadata_depth, maximum=12),
            provider_attempts_per_generation=_env_int("MARY_PROVIDER_ATTEMPTS_PER_GENERATION", defaults.provider_attempts_per_generation, maximum=16),
            paid_calls_per_task=_env_int("MARY_PAID_CALLS_PER_TASK", defaults.paid_calls_per_task, maximum=16),
            expert_max_output_tokens=_env_int("MARY_EXPERT_MAX_OUTPUT_TOKENS", defaults.expert_max_output_tokens, minimum=64, maximum=16_384),
            backup_generations=_env_int("MARY_STATE_BACKUP_GENERATIONS", defaults.backup_generations, minimum=1, maximum=10),
            state_file_soft_limit_bytes=_env_int("MARY_STATE_FILE_SOFT_LIMIT_BYTES", defaults.state_file_soft_limit_bytes, minimum=1024 * 1024, maximum=1024 * 1024 * 1024),
            dialogue_history_capacity=_env_int("MARY_DIALOGUE_HISTORY_CAPACITY", defaults.dialogue_history_capacity, maximum=2_000),
        )

    def to_dict(self) -> dict[str, int]:
        return {name: int(value) for name, value in self.__dict__.items()}
