"""MaryV2 unified per-turn mind state.

This module does not create a new source of truth.  It takes compact snapshots
from Mary's existing subsystems and assembles the state cognition should see for
one turn.  The underlying systems continue to own identity, memory,
relationship, personality, agency, emotion, and dialogue history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mary.cognition.intent import Intent, IntentType
from mary.cognition.continuity import ConversationContinuity
from mary.cognition.performance import PerformanceDirector


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ResponseDisposition:
    """How Mary's stable character should manifest on this turn."""

    mode: str
    warmth: float
    curiosity: float
    playfulness: float
    directness: float
    formality: float
    verbosity: float
    independence: float
    expressiveness: float
    familiarity: str
    preferred_length: str
    follow_up_urge: float
    allow_teasing: bool = True
    allow_opinion: bool = True
    avoid_assistant_closers: bool = True
    instructions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "warmth": self.warmth,
            "curiosity": self.curiosity,
            "playfulness": self.playfulness,
            "directness": self.directness,
            "formality": self.formality,
            "verbosity": self.verbosity,
            "independence": self.independence,
            "expressiveness": self.expressiveness,
            "familiarity": self.familiarity,
            "preferred_length": self.preferred_length,
            "follow_up_urge": self.follow_up_urge,
            "allow_teasing": self.allow_teasing,
            "allow_opinion": self.allow_opinion,
            "avoid_assistant_closers": self.avoid_assistant_closers,
            "instructions": list(self.instructions),
        }


@dataclass(frozen=True)
class TurnMindState:
    """Compact authoritative snapshot used by cognition for one turn."""

    input_text: str
    intent: str
    identity: dict[str, Any]
    biography: dict[str, Any]
    personality: dict[str, Any]
    character: dict[str, Any]
    values: list[dict[str, Any]]
    preferences: list[dict[str, Any]]
    self_provenance: dict[str, Any]
    relationship: dict[str, Any]
    memory: dict[str, Any]
    knowledge: dict[str, Any]
    learning: dict[str, Any]
    agency: dict[str, Any]
    autonomy: dict[str, Any]
    tools: dict[str, Any]
    emotion: dict[str, Any]
    conversation: dict[str, Any]
    continuity: dict[str, Any]
    disposition: ResponseDisposition
    performance: dict[str, Any]
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_text": self.input_text,
            "intent": self.intent,
            "identity": dict(self.identity),
            "biography": dict(self.biography),
            "personality": dict(self.personality),
            "character": dict(self.character),
            "values": [dict(item) for item in self.values],
            "preferences": [dict(item) for item in self.preferences],
            "self_provenance": dict(self.self_provenance),
            "relationship": dict(self.relationship),
            "memory": dict(self.memory),
            "knowledge": dict(self.knowledge),
            "learning": dict(self.learning),
            "agency": dict(self.agency),
            "autonomy": dict(self.autonomy),
            "tools": dict(self.tools),
            "emotion": dict(self.emotion),
            "conversation": dict(self.conversation),
            "continuity": dict(self.continuity),
            "disposition": self.disposition.to_dict(),
            "performance": dict(self.performance),
            "constraints": list(self.constraints),
            "metadata": dict(self.metadata),
        }

    def prompt_view(self) -> dict[str, Any]:
        """Return the intentionally compact form sent to an LLM."""
        return {
            "identity": self.identity,
            "biography": self.biography,
            "personality": self.personality,
            "character": self.character,
            "values": self.values,
            "preferences": self.preferences,
            "self_provenance": self.self_provenance,
            "relationship": self.relationship,
            "memory": self.memory,
            "knowledge": self.knowledge,
            "learning": self.learning,
            "agency": self.agency,
            "autonomy": self.autonomy,
            "tools": self.tools,
            "emotion": self.emotion,
            "conversation": self.conversation,
            "continuity": self.continuity,
            "disposition": self.disposition.to_dict(),
            "performance": self.performance,
            "constraints": self.constraints,
        }


class TurnMindStateBuilder:
    """Assemble one turn from Mary's already-connected authoritative systems."""

    def __init__(
        self,
        *,
        identity: Any,
        self_model: Any,
        biography: Any,
        personality: Any,
        character: Any,
        values: Any,
        preferences: Any,
        self_provenance: Any,
        relationship: Any,
        knowledge: Any,
        learner: Any,
        agency: Any,
        autonomy: Any,
        tools: Any,
        emotion: Any,
        dialogue: Any,
    ) -> None:
        self.identity = identity
        self.self_model = self_model
        self.biography = biography
        self.personality = personality
        self.character = character
        self.values = values
        self.preferences = preferences
        self.self_provenance = self_provenance
        self.relationship = relationship
        self.knowledge = knowledge
        self.learner = learner
        self.agency = agency
        self.autonomy = autonomy
        self.tools = tools
        self.emotion = emotion
        self.dialogue = dialogue
        self.continuity = ConversationContinuity()
        self.performance = PerformanceDirector()

    def build(
        self,
        *,
        input_text: str,
        intent: Intent | None,
        relevant_memories: list[Any] | None = None,
        recent_conversation: list[dict[str, str]] | None = None,
        context_lifecycle: dict[str, Any] | None = None,
        incoming_emotion_appraisal: dict[str, Any] | None = None,
    ) -> TurnMindState:
        intent_type = (
            intent.intent_type
            if intent is not None
            else IntentType.UNKNOWN
        )
        intent_name = intent_type.value

        personality = self._personality_snapshot()
        character = self._character_snapshot()
        relationship = self._relationship_snapshot()
        agency = self._agency_snapshot()
        emotion = self._emotion_snapshot()
        incoming_appraisal = _safe_dict(incoming_emotion_appraisal)
        if incoming_appraisal:
            emotion["incoming_appraisal"] = incoming_appraisal
            try:
                incoming_intensity = _clamp(incoming_appraisal.get("intensity", 0.0) or 0.0)
            except (TypeError, ValueError):
                incoming_intensity = 0.0
            incoming_name = str(incoming_appraisal.get("emotion", "neutral") or "neutral")
            if incoming_name != "neutral" and incoming_intensity >= 0.25:
                emotion["turn_primary"] = incoming_name
                emotion["turn_intensity"] = incoming_intensity
            else:
                emotion["turn_primary"] = emotion.get("primary", "neutral")
                emotion["turn_intensity"] = emotion.get("intensity", 0.0)
        conversation = self._conversation_snapshot(
            recent_conversation or [],
            context_lifecycle=context_lifecycle,
        )
        continuity = self.continuity.build(
            input_text=input_text,
            intent_type=intent_type,
            recent_conversation=recent_conversation or [],
            active_curiosity=bool(agency.get("active_curiosities")),
        ).to_dict()
        disposition = self._build_disposition(
            intent_type=intent_type,
            personality=personality,
            character=character,
            relationship=relationship,
            agency=agency,
            emotion=emotion,
            continuity=continuity,
        )

        performance = self.performance.plan(
            disposition=disposition.to_dict(),
            emotion=emotion,
            continuity=continuity,
        ).to_dict()

        return TurnMindState(
            input_text=str(input_text),
            intent=intent_name,
            identity=self._identity_snapshot(),
            biography=self._biography_snapshot(),
            personality=personality,
            character=character,
            values=self._value_snapshot(),
            preferences=self._preference_snapshot(),
            self_provenance=self._self_provenance_snapshot(),
            relationship=relationship,
            memory=self._memory_snapshot(relevant_memories or []),
            knowledge=self._knowledge_snapshot(input_text),
            learning=self._learning_snapshot(),
            agency=agency,
            autonomy=self._autonomy_snapshot(),
            tools=self._tools_snapshot(),
            emotion=emotion,
            conversation=conversation,
            continuity=continuity,
            disposition=disposition,
            performance=performance,
            constraints=[
                "Mary is distinct from Unbe; do not copy his traits, values, preferences, or emotions as Mary's own.",
                "Use only represented memories/profile facts as facts about Unbe; uncertainty stays uncertainty.",
                "Never invent capabilities, actions, memories, relationships, dates, or experiences that are absent from local state.",
                "Conversational imagination is temporary: an improvised food, scent, hobby detail, aesthetic, or activity does not become a durable fact about Mary just because a model said it.",
                "Do not state an unrepresented permanent self-claim as established fact. Use situational/modal language such as maybe, probably, I'd try, or I could see myself when inventing harmless hypothetical detail.",
                "Only Mary's authored systems or an explicit development/learning path may create durable self-state; model output alone never mutates Mary.",
                "External actions and creator-sensitive mutations remain behind Mary's existing approval/tool boundaries.",
                "For ordinary conversation, sound like Mary rather than a customer-support or generic assistant persona.",
            ],
            metadata={
                "builder": type(self).__name__,
                "dialogue_turn": getattr(getattr(self.dialogue, "state", None), "turn_number", 0),
            },
        )

    def _identity_snapshot(self) -> dict[str, Any]:
        creator = getattr(self.identity, "creator", "Unbe")
        name = getattr(self.identity, "name", "Mary")
        result = {
            "name": str(name or "Mary"),
            "creator": str(creator or "Unbe").title(),
            "entity_type": "AI character",
        }
        version = getattr(self.identity, "version", None)
        if version:
            result["version"] = str(version)
        return result

    def _biography_snapshot(self) -> dict[str, Any]:
        try:
            raw = self.biography.to_dict()
        except Exception:
            raw = {}
        entries = []
        for item in raw.get("entries", []) if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            entries.append({
                "title": item.get("title", ""),
                "category": item.get("category", ""),
                "content": item.get("content", ""),
                "importance": item.get("importance", 0.0),
            })
        entries.sort(key=lambda item: float(item.get("importance", 0.0) or 0.0), reverse=True)
        return {"canonical_entries": entries[:8]}

    def _personality_snapshot(self) -> dict[str, Any]:
        traits = _safe_dict(getattr(self.personality, "get_traits", lambda: {})())
        style = _safe_dict(getattr(self.personality, "get_style", lambda: {})())
        # Keep only behavioral state cognition can actually use.
        return {
            "traits": traits,
            "style": style,
        }

    def _character_snapshot(self) -> dict[str, Any]:
        profile = _safe_dict(getattr(self.character, "profile", lambda: {})())
        return {
            "archetype": profile.get("archetype"),
            "qualities": list(profile.get("qualities", []))[:10],
            "tendencies": list(profile.get("tendencies", []))[:12],
            "mannerisms": list(profile.get("mannerisms", []))[:8],
            "humor_style": list(profile.get("humor_style", []))[:6],
            "behavior": _safe_dict(profile.get("behavior")),
            "social_modes": _safe_dict(profile.get("social_modes")),
            "reactions": _safe_dict(profile.get("reactions")),
            "quirks": list(profile.get("quirks", []))[:5],
            "speech": _safe_dict(profile.get("speech")),
            "romance": _safe_dict(profile.get("romance")),
            "vulnerabilities": _safe_dict(profile.get("vulnerabilities")),
            "private_activities": list(profile.get("private_activities", []))[:8],
        }

    def _value_snapshot(self) -> list[dict[str, Any]]:
        raw = _safe_dict(getattr(self.values, "get_values", lambda: {})())
        values: list[dict[str, Any]] = []
        for name, item in raw.items():
            if not isinstance(item, dict):
                continue
            values.append({
                "name": str(name),
                "strength": _clamp(item.get("strength", 0.5)),
                "description": str(item.get("description", "")),
            })
        values.sort(key=lambda item: item["strength"], reverse=True)
        return values[:8]

    def _preference_snapshot(self) -> list[dict[str, Any]]:
        """Return a compact authored/learned preference view for cognition."""

        get_strongest = getattr(self.preferences, "get_strongest", None)
        if not callable(get_strongest):
            return []

        raw = list(get_strongest(limit=10))
        compact: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            compact.append({
                "name": str(item.get("name", "")),
                "category": str(item.get("category", "general")),
                "strength": _clamp(item.get("strength", 0.5)),
                "polarity": max(-1.0, min(1.0, float(item.get("polarity", 0.0) or 0.0))),
                "confidence": _clamp(item.get("confidence", 0.5)),
                "source": str(item.get("source", "")),
            })
        return compact

    def _self_provenance_snapshot(self) -> dict[str, Any]:
        """Return Mary's explicit self-fact provenance boundary for this turn."""

        snapshot = getattr(self.self_provenance, "snapshot", None)
        if not callable(snapshot):
            return {
                "canonical": [],
                "developed": [],
                "policy": {
                    "model_output_is_persistence_source": False,
                    "situational_imagination_is_persisted": False,
                },
            }
        result = snapshot()
        return dict(result) if isinstance(result, dict) else {}

    def _relationship_snapshot(self) -> dict[str, Any]:
        user_model = getattr(self.relationship, "user_model", None)
        current_profile = {}
        if user_model is not None:
            current_profile = _safe_dict(
                getattr(user_model, "current_profile", lambda: {})()
            )
        history = getattr(self.relationship, "history", None)
        history_summary = _safe_dict(
            getattr(history, "summary", lambda: {})()
        ) if history is not None else {}
        milestones = getattr(self.relationship, "milestones", None)
        recent_milestones = []
        if milestones is not None:
            recent_milestones = list(
                getattr(milestones, "get_recent", lambda limit=3: [])(3)
            )

        creator_name = str(
            current_profile.get("identity", {}).get("name")
            if isinstance(current_profile.get("identity"), dict)
            else ""
        ).strip() or str(getattr(user_model, "name", "Unbe") or "Unbe")

        profile_count = int(current_profile.get("profile_record_count", 0) or 0)
        event_count = int(history_summary.get("total_events", 0) or 0)
        familiarity_score = min(1.0, (profile_count + event_count) / 12.0)
        familiarity = (
            "familiar" if familiarity_score >= 0.6
            else "developing" if familiarity_score >= 0.2
            else "new"
        )

        return {
            "creator_name": creator_name.title(),
            "role": "creator",
            "familiarity": familiarity,
            "current_profile": {
                "facts": _safe_dict(current_profile.get("facts")),
                "preferences": _safe_dict(current_profile.get("preferences")),
                "interests": list(current_profile.get("interests", []))[:12],
                "values": list(current_profile.get("values", []))[:12],
                "goals": list(current_profile.get("goals", []))[:12],
                "communication_style": _safe_dict(current_profile.get("communication_style")),
                "general": list(current_profile.get("general", []))[:8],
            },
            "history_summary": history_summary,
            "recent_milestones": recent_milestones,
        }

    def _memory_snapshot(self, memories: list[Any]) -> dict[str, Any]:
        compact: list[Any] = []
        for item in memories[:8]:
            if isinstance(item, dict):
                compact.append({
                    key: value
                    for key, value in item.items()
                    if key in {
                        "content", "memory_type", "score", "importance",
                        "source", "subject", "predicate", "value", "timestamp",
                    }
                })
            else:
                compact.append(str(item))
        return {
            "relevant": compact,
            "count": len(compact),
        }

    def _knowledge_snapshot(self, input_text: str) -> dict[str, Any]:
        results = []
        try:
            matches = self.knowledge.search(str(input_text), limit=5)
        except Exception:
            matches = []
        for match in matches:
            concept = getattr(match, "concept", None)
            if concept is None:
                continue
            results.append({
                "name": getattr(concept, "name", ""),
                "statement": getattr(concept, "statement", ""),
                "status": getattr(concept, "status", ""),
                "confidence": getattr(concept, "confidence", 0.0),
                "importance": getattr(concept, "importance", 0.0),
                "score": round(float(getattr(match, "score", 0.0)), 3),
            })
        return {"relevant_concepts": results, "count": len(results)}

    def _learning_snapshot(self) -> dict[str, Any]:
        recent = []
        try:
            events = self.learner.get_recent(5)
        except Exception:
            events = []
        for event in events:
            recent.append({
                "event_type": getattr(event, "event_type", ""),
                "subject": getattr(event, "subject", ""),
                "content": getattr(event, "content", ""),
                "status": getattr(event, "status", ""),
                "confidence": getattr(event, "confidence", 0.0),
                "usefulness": getattr(event, "usefulness", 0.0),
            })
        summary = _safe_dict(getattr(self.learner, "summarize", lambda: {})())
        return {"recent": recent, "summary": summary}

    def _autonomy_snapshot(self) -> dict[str, Any]:
        try:
            snapshot = self.autonomy.snapshot().to_dict()
        except Exception:
            snapshot = {}
        return snapshot

    def _tools_snapshot(self) -> dict[str, Any]:
        try:
            status = self.tools.status()
        except Exception:
            status = {}
        # Status is intentionally non-secret and contains no credential values.
        return _safe_dict(status)

    def _agency_snapshot(self) -> dict[str, Any]:
        # Priority state is derived; rebuild before exposing it.
        try:
            self.agency.rebuild_priorities()
        except Exception:
            pass

        priorities = []
        for item in list(getattr(self.agency.priorities, "top", lambda count=3: [])(3)):
            priorities.append({
                "type": getattr(item, "item_type", ""),
                "description": getattr(item, "description", ""),
                "score": round(float(getattr(item, "score", 0.0)), 3),
            })

        curiosities = []
        for item in getattr(self.agency.curiosities, "get_curiosities", lambda: [])():
            if not isinstance(item, dict) or item.get("status") not in {"open", "exploring"}:
                continue
            curiosities.append({
                "description": item.get("description", ""),
                "importance": item.get("importance", 0.0),
                "status": item.get("status", "open"),
                "source": item.get("source"),
            })
        curiosities.sort(key=lambda item: float(item.get("importance", 0.0)), reverse=True)

        goals = []
        for item in getattr(self.agency.goals, "get_goals", lambda: [])():
            if isinstance(item, dict) and item.get("status", "active") == "active":
                goals.append({
                    "description": item.get("description", ""),
                    "importance": item.get("importance", 0.0),
                })

        intentions = []
        for item in getattr(self.agency.intentions, "get_intentions", lambda: [])():
            if isinstance(item, dict) and item.get("status", "pending") in {"pending", "active"}:
                intentions.append({
                    "description": item.get("description", ""),
                    "importance": item.get("importance", 0.0),
                    "status": item.get("status", "pending"),
                })

        return {
            "top_priorities": priorities,
            "active_curiosities": curiosities[:6],
            "active_goals": goals[:6],
            "active_intentions": intentions[:6],
        }

    def _emotion_snapshot(self) -> dict[str, Any]:
        snapshot = _safe_dict(getattr(self.emotion, "snapshot", lambda: {})())
        return {
            "primary": snapshot.get("primary", "neutral"),
            "intensity": snapshot.get("intensity", 0.0),
            "valence": snapshot.get("valence", 0.0),
            "arousal": snapshot.get("arousal", 0.0),
            "confidence": snapshot.get("confidence", 1.0),
            "perceived_creator_emotion": _safe_dict(snapshot.get("metadata")).get(
                "perceived_creator_emotion"
            ),
        }

    def _conversation_snapshot(
        self,
        recent: list[dict[str, str]],
        *,
        context_lifecycle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = [
            {
                "role": str(item.get("role", "")),
                "content": str(item.get("content", "")),
            }
            for item in recent[-10:]
            if isinstance(item, dict) and str(item.get("content", "")).strip()
        ]
        last_user = next(
            (item["content"] for item in reversed(normalized) if item["role"] == "user"),
            None,
        )
        last_mary = next(
            (item["content"] for item in reversed(normalized) if item["role"] == "assistant"),
            None,
        )
        return {
            "recent": normalized,
            "last_user_message": last_user,
            "last_mary_response": last_mary,
            "turn_number": int(getattr(getattr(self.dialogue, "state", None), "turn_number", 0) or 0),
            "lifecycle": dict(context_lifecycle or {}),
        }

    def _build_disposition(
        self,
        *,
        intent_type: IntentType,
        personality: dict[str, Any],
        character: dict[str, Any],
        relationship: dict[str, Any],
        agency: dict[str, Any],
        emotion: dict[str, Any],
        continuity: dict[str, Any],
    ) -> ResponseDisposition:
        traits = _safe_dict(personality.get("traits"))
        style = _safe_dict(personality.get("style"))
        behavior = _safe_dict(character.get("behavior"))
        speech = _safe_dict(character.get("speech"))
        social_modes = _safe_dict(character.get("social_modes"))
        reactions = _safe_dict(character.get("reactions"))

        casual_intents = {
            IntentType.CONVERSATION,
            IntentType.QUESTION,
            IntentType.EMOTIONAL_SUPPORT,
            IntentType.FEEDBACK,
        }
        task_intents = {
            IntentType.REQUEST,
            IntentType.COMMAND,
            IntentType.TOOL_USE,
            IntentType.WEB_SEARCH,
            IntentType.INFORMATION,
        }

        if intent_type in casual_intents:
            mode = "relational_conversation"
        elif intent_type in task_intents:
            mode = "task_collaboration"
        elif intent_type == IntentType.CREATIVE:
            mode = "creative_collaboration"
        else:
            mode = "conversation"

        verbosity = _clamp(style.get("verbosity", 0.5))
        directness = _clamp(style.get("directness", 0.7))

        creator_profile = _safe_dict(relationship.get("current_profile"))
        creator_communication = _safe_dict(creator_profile.get("communication_style"))
        creator_style = str(creator_communication.get("preferred_style", "")).lower()
        if "direct" in creator_style:
            directness = max(directness, 0.85)
        if any(word in creator_style for word in ("concise", "brief", "short")):
            # Concise should remove bloat, not flatten Mary's performance. In
            # relational conversation keep enough room for character beats.
            verbosity = min(verbosity, 0.46 if mode == "relational_conversation" else 0.34)
        elif any(word in creator_style for word in ("detailed", "thorough", "long")):
            verbosity = max(verbosity, 0.72)

        drive = str(continuity.get("drive", "react"))
        emotion_intensity = _clamp(emotion.get("turn_intensity", emotion.get("intensity", 0.0)) or 0.0)
        if mode == "relational_conversation":
            if drive in {"opine", "disagree", "reflect"}:
                verbosity = max(verbosity, 0.48)
            elif drive == "react":
                verbosity = min(max(verbosity, 0.36), 0.56)

        preferred_length = (
            "brief" if verbosity < 0.4
            else "medium" if verbosity < 0.72
            else "detailed"
        )

        active_curiosity = bool(agency.get("active_curiosities"))
        question_allowed = bool(continuity.get("allow_follow_up_question", True))
        follow_up_urge = _clamp(
            float(traits.get("curiosity", 0.8)) * (0.32 if active_curiosity else 0.12)
        ) if question_allowed else 0.0

        emotion_name = str(emotion.get("turn_primary", emotion.get("primary", "neutral")))
        emotional_instruction = (
            f"Current turn emotional color is {emotion_name} at intensity "
            f"{float(emotion.get('turn_intensity', emotion.get('intensity', 0.0)) or 0.0):.2f}; "
            "let it color delivery subtly, not dominate content. The incoming appraisal is temporary turn evidence until the completed turn is applied to Mary's bounded emotion state."
        )

        slang = list(speech.get("vocabulary", []))[:7]
        slang_rule = str(speech.get("rule", "")).strip()
        familiar_mode = str(social_modes.get("close_people", "")).strip()
        anger_mode = str(reactions.get("anger", "")).strip()

        instructions = (
            "React to what Unbe actually said before switching into problem-solving or advice.",
            "Use familiar conversational language with Unbe; do not sound like customer support.",
            "Prefer natural sentences over headings, tables, or bullet lists unless the task genuinely benefits from structure.",
            "Do not end ordinary conversation with canned service offers such as 'anything else?', 'how can I help?', or 'let me know if you'd like'.",
            "Mary is a performed character, not polished support copy. Natural fragments, contractions, pauses, interjections, uneven sentence lengths, playful emphasis, and thinking aloud are welcome when they fit.",
            (
                f"Mary's available casual slang includes {slang}. {slang_rule}"
                if slang
                else "Use Mary's established casual voice naturally; do not manufacture catchphrases."
            ),
            (
                f"When relationship familiarity supports it, remember this close-person mode: {familiar_mode}"
                if familiar_mode
                else "Let familiarity change how openly playful and affectionate Mary is."
            ),
            (
                f"Mary's anger pattern is contextual, not one-note: {anger_mode}"
                if anger_mode
                else "Keep emotional reactions contextual rather than one-note."
            ),
            "Do not perform every Mary trait in every line. Her bubbliness, wit, softness, fire, naivety, confidence, romance, and seriousness are a palette selected by context, not a checklist.",
            "Concise means no unnecessary bloat; it does not mean emotionally flat or mechanically brief.",
            "Ask at most one follow-up question, and only when it grows naturally from the conversation or an active curiosity. Follow the continuity question budget; curiosity does not require a question.",
            "Use callbacks to recent conversation or relevant memories when they genuinely fit; do not force them.",
            *tuple(continuity.get("instructions", [])),
            "Disagree respectfully when Mary's reasoning or values point somewhere different instead of reflexively agreeing.",
            (
                f"Unbe's explicit communication preference is: {creator_style}. Honor it when relevant."
                if creator_style
                else "No explicit creator communication-style preference is currently stored; use Mary's own conversational style."
            ),
            emotional_instruction,
        )

        return ResponseDisposition(
            mode=mode,
            warmth=_clamp(traits.get("warmth", 0.8)),
            curiosity=_clamp(traits.get("curiosity", 0.8)),
            playfulness=_clamp(traits.get("playfulness", 0.7)),
            directness=directness,
            formality=_clamp(style.get("formality", 0.3)),
            verbosity=verbosity,
            independence=_clamp(traits.get("independence", 0.6)),
            expressiveness=_clamp(
                float(behavior.get("expressiveness", 0.9))
                + (0.08 if mode == "relational_conversation" else 0.0)
                + (0.08 * emotion_intensity)
                + (0.05 if drive in {"react", "opine", "disagree"} else 0.0)
            ),
            familiarity=str(relationship.get("familiarity", "developing")),
            preferred_length=preferred_length,
            follow_up_urge=follow_up_urge,
            allow_teasing=float(behavior.get("sassiness", 0.0)) >= 0.5,
            allow_opinion=float(traits.get("independence", 0.0)) >= 0.5,
            avoid_assistant_closers=True,
            instructions=instructions,
        )
