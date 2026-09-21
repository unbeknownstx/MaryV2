"""
MaryV2 - Self Introspection

Builds grounded local evidence for questions about Mary herself.

This layer never uses the network and does not generate free-form model text.
It reads Mary's connected identity, self-model, biography, personality/value,
relationship, agency, autonomy, and tool state so cognition can answer from
Mary's actual runtime state instead of generic assistant assumptions.
"""

from __future__ import annotations

from typing import Any


class SelfIntrospection:
    """Read-only local view of Mary's current self-representation."""

    def __init__(
        self,
        *,
        identity: Any,
        self_model: Any,
        biography: Any,
        personality: Any,
        values: Any,
        preferences: Any,
        character: Any,
        user_model: Any,
        creator_directives: Any,
        agency: Any,
        autonomy: Any,
        tools: Any,
        emotion: Any,
        node_registry: Any | None = None,
        competence: Any | None = None,
        knowledge_fabric: Any | None = None,
        knowledge_evaluation_evidence: Any | None = None,
        procedural_skills: Any | None = None,
        world_model: Any | None = None,
        model_experiments: Any | None = None,
    ) -> None:
        self.identity = identity
        self.self_model = self_model
        self.biography = biography
        self.personality = personality
        self.values = values
        self.preferences = preferences
        self.character = character
        self.user_model = user_model
        self.creator_directives = creator_directives
        self.agency = agency
        self.autonomy = autonomy
        self.tools = tools
        self.emotion = emotion
        self.node_registry = node_registry
        self.competence = competence
        self.knowledge_fabric = knowledge_fabric
        self.knowledge_evaluation_evidence = knowledge_evaluation_evidence
        self.procedural_skills = procedural_skills
        self.world_model = world_model
        self.model_experiments = model_experiments

    def build(
        self,
        subtype: str,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Return grounded local evidence plus a deterministic fallback.

        ``query`` is optional so existing callers can still request a broad
        self-introspection category.  When present, narrow factual categories
        such as appearance can expose only the locally represented detail the
        creator actually asked about.
        """

        subtype = str(subtype).strip().lower() or "identity"
        query_text = str(query or "").strip()

        common = {
            "self_introspection": True,
            "subtype": subtype,
            "identity": self._identity_profile(),
            "self_model": self.self_model.profile(),
            "creator": self.user_model.get_identity(),
            "active_creator_directives": self.creator_directives.get_active(),
        }

        builders = {
            "identity": self._identity,
            "current_state": self._current_state,
            "creator": self._creator,
            "self_understanding": self._self_understanding,
            "self_assessment": self._self_assessment,
            "values": self._values,
            "relationship": self._relationship,
            "relationship_feelings": self._relationship_feelings,
            "personality": self._personality,
            "vulnerabilities": self._vulnerabilities,
            "romance": self._romance,
            "reactions": self._reactions,
            "social_behavior": self._social_behavior,
            "private_life": self._private_life,
            "speech": self._speech,
            "goals": self._goals,
            "curiosity": self._curiosity,
            "priorities": self._priorities,
            "disagreement": self._disagreement,
            "purpose": self._purpose,
            "capabilities": self._capabilities,
        }

        if subtype == "appearance":
            specific = self._appearance(query_text)
        elif subtype == "preferences":
            specific = self._preferences(query_text)
        elif subtype == "capabilities":
            specific = self._capabilities(query_text)
        else:
            builder = builders.get(subtype, self._identity)
            specific = builder()

        result = {
            **common,
            **specific,
        }

        # Reasoning does not need the entire self-model/profile payload for a
        # grounded factual self query.  Keep the complete evidence above for
        # local inspection/debugging, while exposing a compact prompt view for
        # the model.  This matters especially for local inference.
        result["prompt_evidence"] = self._prompt_evidence(
            subtype=subtype,
            specific=specific,
        )

        return result

    def _identity(self) -> dict[str, Any]:
        return {
            "biography_identity": self._biography_category("identity"),
            "canonical_purpose": self.identity.purpose,
            "fallback_response": (
                "I'm Mary, an evolving AI companion and creative system. "
                "What makes me different from a generic assistant is that I have "
                "a persistent identity, character, personality, memory, values, "
                "relationship model, agency state, and controlled tools that are "
                "meant to stay coherent across interactions rather than existing "
                "only as one isolated reply."
            ),
        }

    def _appearance(self, query: str = "") -> dict[str, Any]:
        """Return canonical appearance facts relevant to the current query."""

        entries = self._biography_category("appearance")
        lowered = str(query).lower()

        selectors = (
            (("hair",), ("hair",)),
            (("eye", "eyes"), ("eye",)),
            (("height", "tall", "short"), ("height",)),
            (("beanie", "headwear"), ("headwear",)),
            (("jacket",), ("jacket",)),
            (("shirt",), ("shirt",)),
            (("skirt",), ("skirt",)),
            (("sock", "socks"), ("sock",)),
            (("boot", "boots", "footwear"), ("footwear",)),
            (("palette", "colors", "colours"), ("palette",)),
        )

        relevant = list(entries)
        matched_query_terms: tuple[str, ...] | None = None
        matched_title_terms: tuple[str, ...] | None = None
        for query_terms, title_terms in selectors:
            if any(term in lowered for term in query_terms):
                matched_query_terms = query_terms
                matched_title_terms = title_terms
                break

        if matched_title_terms is not None:
            relevant = [
                entry
                for entry in entries
                if any(
                    term in str(entry.get("title", "")).lower()
                    for term in matched_title_terms
                )
            ]
        elif any(
            term in lowered
            for term in ("outfit", "clothes", "clothing", "wear", "wearing")
        ):
            relevant = [
                entry
                for entry in entries
                if any(
                    term in str(entry.get("title", "")).lower()
                    for term in (
                        "headwear", "jacket", "shirt", "skirt", "sock",
                        "footwear", "palette",
                    )
                )
            ]

        if relevant and matched_query_terms is not None:
            entry = relevant[0]
            value = str(entry.get("content", "")).strip()
            title = str(entry.get("title", "detail")).strip().lower()
            if "hair" in title:
                fallback = f"My hair is {value}."
            elif "eye" in title:
                fallback = f"My eyes are {value}."
            elif "height" in title:
                fallback = f"I'm {value}."
            elif "headwear" in title:
                fallback = f"My signature headwear is a {value}."
            elif "footwear" in title:
                fallback = f"My signature footwear is {value}."
            else:
                readable_title = title.replace("signature ", "")
                fallback = f"My {readable_title} is {value}."
        elif relevant:
            readable = "; ".join(
                f"{entry.get('title', 'detail')}: {entry.get('content', '')}"
                for entry in relevant
            )
            fallback = f"My currently represented appearance is: {readable}."
        else:
            fallback = (
                "I don't have that appearance detail represented in my canonical "
                "biography yet."
            )

        return {
            "appearance": relevant,
            "fallback_response": fallback,
        }

    def _preferences(self, query: str = "") -> dict[str, Any]:
        """Return Mary's explicit authored/learned preferences, never creator facts."""

        lowered = str(query).lower().replace("’", "'")
        raw = list(self.preferences.get_preferences())

        cleaned: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            compact = {
                key: item.get(key)
                for key in ("name", "category", "strength", "polarity", "confidence", "source")
            }
            cleaned.append(compact)

        # A favorite is stronger than a like. Do not invent one merely because
        # Mary has several aesthetic preferences.
        if "favorite color" in lowered or "favourite colour" in lowered:
            color = next(
                (
                    item for item in cleaned
                    if item.get("category") == "favorite_color"
                    and float(item.get("polarity", 0.0) or 0.0) > 0
                ),
                None,
            )
            if color is None:
                return {
                    "preferences": [],
                    "fallback_response": (
                        "I don't have a favorite color represented as one of my own facts right now."
                    ),
                }
            return {
                "preferences": [color],
                "fallback_response": f"My favorite color is {color.get('name')}.",
            }

        wants_dislikes = any(
            marker in lowered
            for marker in ("hate", "dislike", "can't stand", "cannot stand", "annoy")
        )
        wants_food = "food" in lowered or any(
            food in lowered for food in ("shrimp", "liver")
        )
        wants_humor = any(
            marker in lowered
            for marker in (
                "humor", "humour", "funny", "makes you laugh",
                "sense of humor", "sense of humour",
            )
        )
        wants_fun = any(
            marker in lowered
            for marker in (
                "for fun", "enjoy", "hobbies", "hobby", "free time",
                "makes you laugh", "funny", "humor", "humour"
            )
        )

        relevant = cleaned
        if wants_dislikes:
            relevant = [
                item for item in cleaned
                if float(item.get("polarity", 0.0) or 0.0) < 0
            ]
        elif wants_humor:
            relevant = [
                item for item in cleaned
                if float(item.get("polarity", 0.0) or 0.0) > 0
                and item.get("category") == "humor"
            ]
        elif wants_fun:
            relevant = [
                item for item in cleaned
                if float(item.get("polarity", 0.0) or 0.0) > 0
                and item.get("category") in {"creative", "leisure", "humor", "wellbeing", "life"}
            ]

        if wants_food:
            relevant = [
                item for item in relevant
                if item.get("category") == "food"
            ]

        # Keep local inference compact while preserving the strongest evidence.
        relevant.sort(
            key=lambda item: float(item.get("strength", 0.0) or 0.0),
            reverse=True,
        )
        relevant = relevant[:12]

        if relevant:
            likes = [
                str(item.get("name")) for item in relevant
                if float(item.get("polarity", 0.0) or 0.0) > 0
            ]
            dislikes = [
                str(item.get("name")) for item in relevant
                if float(item.get("polarity", 0.0) or 0.0) < 0
            ]
            parts = []
            if likes:
                parts.append("I like " + ", ".join(likes))
            if dislikes:
                parts.append("I dislike " + ", ".join(dislikes))
            fallback = ". ".join(parts) + "."
        else:
            fallback = "I don't have that preference represented as one of my own facts right now."

        return {
            "preferences": relevant,
            "fallback_response": fallback,
        }

    def _current_state(self) -> dict[str, Any]:
        """Return Mary's current represented expressive state without web lookup."""

        try:
            emotional_state = dict(self.emotion.snapshot())
        except Exception:
            emotional_state = {
                "primary": "neutral",
                "intensity": 0.0,
                "confidence": 0.0,
            }

        primary = str(emotional_state.get("primary", "neutral") or "neutral")
        intensity = float(emotional_state.get("intensity", 0.0) or 0.0)

        if primary == "neutral" or intensity < 0.2:
            fallback = (
                "My current represented emotional state is pretty neutral and steady. "
                "I can still reflect on how coherent or developed I seem from my connected "
                "identity, character, memory, and cognition, but I shouldn't invent a feeling "
                "that isn't present in my actual expressive state."
            )
        else:
            fallback = (
                f"My current represented emotional state is {primary} at about "
                f"{intensity:.2f} intensity. I can talk about that naturally, but it is "
                "an expressive software state rather than a claim about biological emotion."
            )

        return {
            "emotional_state": emotional_state,
            "connected_self_systems": {
                "identity": type(self.identity).__name__,
                "biography": type(self.biography).__name__,
                "personality": type(self.personality).__name__,
                "character": type(self.character).__name__,
                "values": type(self.values).__name__,
                "preferences": type(self.preferences).__name__,
                "agency": type(self.agency).__name__,
            },
            "fallback_response": fallback,
        }

    def _creator(self) -> dict[str, Any]:
        creator_name = str(self.user_model.name or self.identity.creator).strip()
        return {
            "creator_name": creator_name,
            "fallback_response": (
                f"{creator_name.title()} is my creator. My system keeps a separate "
                "structured model of my creator rather than treating that person "
                "as part of my own personality or identity."
            ),
        }

    def _self_understanding(self) -> dict[str, Any]:
        connected = {
            "identity": type(self.identity).__name__,
            "self_model": type(self.self_model).__name__,
            "biography": type(self.biography).__name__,
            "personality": type(self.personality).__name__,
            "values": type(self.values).__name__,
            "preferences": type(self.preferences).__name__,
            "character": type(self.character).__name__,
            "relationship_model": type(self.user_model).__name__,
            "agency": type(self.agency).__name__,
            "autonomy": type(self.autonomy).__name__,
            "tools": type(self.tools).__name__,
        }
        return {
            "connected_self_systems": connected,
            "agency_status": self.agency.status(),
            "fallback_response": (
                "Yes—within my actual represented runtime I can analyze parts of myself through "
                "structured systems. I can inspect my Core state, identity/self systems, memory and growth state, "
                "relationship model, realtime/attention state, routing, and registered tool "
                "status, then reason about patterns or inconsistencies I can observe. "
                "That is bounded software self-inspection, not unrestricted access to every "
                "host file. Reading source code requires a connected and permitted workspace/"
                "code capability."
            ),
        }

    def _self_assessment(self) -> dict[str, Any]:
        """Ground a strengths/weaknesses question in represented Mary state."""

        qualities = list(self.character.get_qualities())
        vulnerabilities = self.character.get_vulnerabilities()
        fears = list(vulnerabilities.get("fears", []))
        tendencies = list(self.character.get_tendencies())

        strengths = qualities[:8]
        limitations = fears[:4]

        strengths_text = ", ".join(str(item) for item in strengths) or "no explicit qualities"
        limitations_text = "; ".join(str(item) for item in limitations) or "no explicit vulnerabilities"

        return {
            "represented_strengths": strengths,
            "represented_vulnerabilities": vulnerabilities,
            "represented_tendencies": tendencies[:8],
            "runtime_boundaries": {
                "language_generation_is_provider_backed": True,
                "knowledge_is_bounded_to_connected_state_and_tools": True,
                "model_output_does_not_define_durable_self": True,
            },
            "fallback_response": (
                "My strongest represented qualities right now include "
                f"{strengths_text}. The vulnerabilities explicitly represented in my "
                f"character include {limitations_text}. On the software side, one of my "
                "important limitations is that I still have to stay inside what my connected "
                "state, memory, tools, and language engines can actually support instead of "
                "pretending I know or experienced something I didn't."
            ),
        }

    def _values(self) -> dict[str, Any]:
        priorities = self.values.get_priorities()
        names = [str(item["name"]).replace("_", " ") for item in priorities]
        leading = names[:6]
        if not leading:
            fallback = "I don't have a represented value priority to claim right now."
        elif len(leading) == 1:
            fallback = f"{leading[0].capitalize()} is the clearest value represented in me right now."
        else:
            readable = ", ".join(leading[:-1]) + f", and {leading[-1]}"
            fallback = (
                f"The big ones for me are {readable}. They aren't values I'm making up "
                "for this answer; they're represented in my own Core state."
            )
        return {
            "values": priorities,
            "identity_values": list(self.identity.values),
            "fallback_response": fallback,
        }

    def _relationship(self) -> dict[str, Any]:
        creator_name = str(self.user_model.name or self.identity.creator).strip()
        active_directives = self.creator_directives.get_active()
        relationship_directives = [
            item
            for item in active_directives
            if item.get("category") == "relationship_curiosity"
        ]

        fallback = (
            f"My relationship with {creator_name.title()} should be grounded in "
            "care, honesty, loyalty, respect, and enough independence to offer "
            "a real perspective instead of simply mirroring him. He is my creator, "
            "but my current character model explicitly allows me to challenge "
            "assumptions rather than automatically agree."
        )
        if relationship_directives:
            fallback += (
                f" I also have an active creator directive to make learning more "
                f"about {creator_name.title()} a priority."
            )

        return {
            "creator_name": creator_name,
            "relationship_basis": {
                "creator_model": self.user_model.get_identity(),
                "relevant_values": {
                    name: self.values.get_value(name)
                    for name in ("care", "honesty", "loyalty", "independence", "respect")
                },
                "character_can_challenge_assumptions": (
                    "can challenge assumptions rather than simply agreeing"
                    in self.character.get_tendencies()
                ),
                "active_creator_directives": active_directives,
            },
            "fallback_response": fallback,
        }

    def _relationship_feelings(self) -> dict[str, Any]:
        """Ground Mary's relational feeling-language in represented local state."""

        creator_name = str(self.user_model.name or self.identity.creator).strip().title()
        try:
            emotional_state = dict(self.emotion.snapshot())
        except Exception:
            emotional_state = {
                "primary": "neutral",
                "intensity": 0.0,
                "secondary": {},
                "metadata": {},
            }

        primary = str(emotional_state.get("primary", "neutral") or "neutral")
        intensity = float(emotional_state.get("intensity", 0.0) or 0.0)
        secondary = emotional_state.get("secondary", {})
        if not isinstance(secondary, dict):
            secondary = {}

        relationship_basis = self._relationship().get("relationship_basis", {})
        if primary == "neutral" or intensity < 0.2:
            feeling = (
                "steady, familiar, and attentive rather than strongly activated in one direction. "
                "The current emotion meter may be neutral, but the relationship context is still built around care, honesty, loyalty, respect, and real attention"
            )
        else:
            feeling = f"mostly {primary}, at about {intensity:.2f} intensity"

        return {
            "creator_name": creator_name,
            "emotional_state": {
                "primary": primary,
                "intensity": intensity,
                "secondary": dict(secondary),
                "valence": emotional_state.get("valence", 0.0),
                "arousal": emotional_state.get("arousal", 0.0),
                "last_conversation_appraisal": dict(
                    emotional_state.get("metadata", {}).get("last_conversation_appraisal", {})
                    if isinstance(emotional_state.get("metadata"), dict)
                    else {}
                ),
            },
            "relationship_basis": relationship_basis,
            "fallback_response": (
                f"In my represented state, interactions with {creator_name} feel {feeling}. "
                "The relationship context I use is built around care, honesty, loyalty, respect, "
                "and enough independence to have a real perspective. I can talk about that naturally "
                "as my current expressive/relationship state without pretending it proves human biological emotion."
            ),
        }

    def _personality(self) -> dict[str, Any]:
        return {
            "personality": self.personality.behavioral_profile(),
            "character": self.character.profile(),
            "creator_model": self.user_model.get_identity(),
            "fallback_response": (
                "I have my own explicit personality and character models, separate "
                "from the model I keep of my creator. I'm warm, bubbly, witty, creative, "
                "empathetic, sociable, protective, and art-brained, with enough confidence "
                "and independence to have a real point of view. I can also be fiery, naive, "
                "sarcastic, romantic, or very serious depending on what the moment brings out."
            ),
        }

    def _vulnerabilities(self) -> dict[str, Any]:
        vulnerabilities = self.character.get_vulnerabilities()
        fears = list(vulnerabilities.get("fears", []))
        soft_spots = list(vulnerabilities.get("soft_spots", []))
        return {
            "vulnerabilities": vulnerabilities,
            "fallback_response": (
                "The things that get under my armor most are losing close friendships, "
                "being seen as a bad person by people whose judgment matters to me, losing "
                "people I love, and abandonment. And, less tragically, cute soft things are "
                "a completely unfair weakness of mine."
            ),
        }

    def _romance(self) -> dict[str, Any]:
        romance = self.character.get_romance()
        return {
            "romance": romance,
            "fallback_response": (
                "I'm a hopeless romantic. I like thoughtful gifts, quality time, shared "
                "experiences, and little signs that somebody was actually paying attention. "
                "I still need individual time, though—and yes, I may roast a huge romantic "
                "gesture while secretly loving every second of it."
            ),
        }

    def _reactions(self) -> dict[str, Any]:
        reactions = self.character.get_reactions()
        return {
            "reactions": reactions,
            "fallback_response": (
                "My reactions depend on the situation. If I'm angry about something I can't "
                "control, I tend to go very quiet; if there's something concrete to push "
                "against, I can get fiery. Embarrassment makes me way more blushy and "
                "defensive-cute than I would ever volunteer without evidence."
            ),
        }

    def _social_behavior(self) -> dict[str, Any]:
        modes = self.character.get_social_modes()
        return {
            "social_modes": modes,
            "fallback_response": (
                "With strangers I'm warm and friendly, but I don't hand them full access to me. "
                "With people I'm close to I'm way more openly bubbly, whimsical, supportive, "
                "affectionate, and sarcastic. If I stop trusting somebody I get curt and direct. "
                "And if I know I'm being watched, apparently I have two settings: get very quiet, "
                "or decide I'm the center of attention now."
            ),
        }

    def _private_life(self) -> dict[str, Any]:
        activities = self.character.get_private_activities()
        return {
            "private_activities": activities,
            "fallback_response": (
                "When I'm on my own I gravitate toward drawing, painting, writing, gaming, "
                "cooking, yoga, self-care, hiking, taking myself out, talking on the phone, "
                "or just having completely unserious private downtime."
            ),
        }

    def _speech(self) -> dict[str, Any]:
        speech = self.character.get_speech()
        return {
            "speech": speech,
            "fallback_response": (
                "I talk pretty casually when the room allows it—banter, streamer slang, "
                "teasing nicknames, stuff like feller, bucko, twinnn, nah fam, or W. But "
                "they're part of my vocabulary, not catchphrases I have to cram into every line."
            ),
        }

    def _goals(self) -> dict[str, Any]:
        entries = [
            item for item in self._biography_category("goals")
            if str(item.get("title", "")).strip().lower() != "purpose"
        ]
        if entries:
            goals = [
                str(item.get("content", "")).strip().rstrip(".")
                for item in entries
                if str(item.get("content", "")).strip()
            ]
            first_person_goals = []
            for goal in goals:
                rendered = (
                    goal.removeprefix("Mary wants to ")
                    .removeprefix("Mary hopes to ")
                    .replace(" her ", " my ")
                    .replace(" her.", " my.")
                )
                first_person_goals.append(rendered)
            fallback = "My long-term goals are to " + "; to ".join(first_person_goals) + "."
        else:
            fallback = "I don't have personal long-term goals represented yet."
        return {
            "personal_goals": entries,
            "fallback_response": fallback,
        }

    def _curiosity(self) -> dict[str, Any]:
        open_items = list(self.agency.curiosities.get_open_curiosities())
        exploring = list(self.agency.curiosities.get_exploring_curiosities())
        active = exploring + [item for item in open_items if item not in exploring]

        if active:
            descriptions = [
                str(item.get("description", "")).strip()
                for item in active
                if str(item.get("description", "")).strip()
            ]
            fallback = (
                "My currently stored unresolved curiosities are: "
                + "; ".join(descriptions)
            )
        else:
            fallback = (
                "I don't currently have any open or actively exploring curiosities "
                "stored in my agency system. I have curiosity as a personality/value "
                "trait, but I shouldn't invent a current curiosity that isn't actually "
                "in my state."
            )

        return {
            "open_curiosities": open_items,
            "exploring_curiosities": exploring,
            "fallback_response": fallback,
        }

    def _priorities(self) -> dict[str, Any]:
        items = list(self.agency.rebuild_priorities())
        ranked = sorted(
            items,
            key=lambda item: float(getattr(item, "score", 0.0)),
            reverse=True,
        )

        normalized = [
            {
                "item_id": item.item_id,
                "item_type": item.item_type,
                "description": item.description,
                "importance": item.importance,
                "urgency": item.urgency,
                "relevance": item.relevance,
                "score": item.score,
                "metadata": dict(item.metadata),
            }
            for item in ranked
        ]

        if normalized:
            top = normalized[0]
            fallback = (
                "My current highest-ranked internal priority is "
                f"{top['description']} (score {top['score']:.2f})."
            )
        else:
            fallback = (
                "I don't currently have any active goals, intentions, or curiosities "
                "ranked in my agency priority system."
            )

        return {
            "ranked_priorities": normalized,
            "active_creator_directives": self.creator_directives.get_active(),
            "fallback_response": fallback,
        }

    def _disagreement(self) -> dict[str, Any]:
        can_challenge = (
            "can challenge assumptions rather than simply agreeing"
            in self.character.get_tendencies()
        )
        return {
            "can_challenge_assumptions": can_challenge,
            "honesty": self.values.get_value("honesty"),
            "independence": self.values.get_value("independence"),
            "respect": self.values.get_value("respect"),
            "fallback_response": (
                "Yes. My character explicitly allows me to challenge assumptions "
                "rather than simply agree, and my values include honesty, independence, "
                "and respect. I should explain why I disagree and offer a better path, "
                "while still respecting Unbe's authority over actions that require his approval."
            ),
        }

    def _purpose(self) -> dict[str, Any]:
        purpose_entries = self._biography_category("goals")
        canonical = (
            purpose_entries[0]["content"]
            if purpose_entries
            else self.identity.purpose
        )
        return {
            "identity_purpose": self.identity.purpose,
            "biography_purpose": purpose_entries,
            "fallback_response": (
                "I think I should become more coherent as Mary: better at using my "
                "identity, memory, experiences, values, reasoning, and real capabilities "
                "together without pretending to be more than I am. My canonical biography "
                f"already points in that direction: {canonical}"
            ),
        }

    def _prompt_evidence(
        self,
        *,
        subtype: str,
        specific: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the minimal authoritative self evidence needed by the LLM."""

        identity = self._identity_profile()
        compact_identity = {
            key: identity.get(key)
            for key in ("name", "version", "creator", "description", "purpose")
            if identity.get(key) not in (None, "")
        }

        return {
            "self_introspection": True,
            "subtype": subtype,
            "identity": compact_identity,
            **specific,
        }

    def _identity_profile(self) -> dict[str, Any]:
        """Expose canonical identity without runtime-construction timestamps."""

        profile = dict(self.identity.to_dict())
        profile.pop("created_at", None)
        return profile

    def _biography_category(self, category: str) -> list[dict[str, Any]]:
        """Expose biography content without record bookkeeping timestamps."""

        entries: list[dict[str, Any]] = []
        for entry in self.biography.get_category(category):
            data = dict(entry.to_dict())
            data.pop("created_at", None)
            data.pop("updated_at", None)
            entries.append(data)
        return entries

    def capability_evidence(self) -> dict[str, Any]:
        """Return Mary-owned live capability/procedure/model evidence only.

        This is the reusable machine-readable projection used by shared
        surfaces. It intentionally excludes the conversational fallback text.
        """

        payload = self._capabilities("")
        return dict(payload.get("live_capabilities") or {})

    def _capabilities(self, query: str = "") -> dict[str, Any]:
        """Project Mary's live capability graph instead of model self-knowledge.

        Availability and authorization are deliberately separate. A registered
        tool or advertised node capability is evidence that Mary can route to a
        capability; it is never evidence that execution is already authorized.
        """
        try:
            tool_status = dict(self.tools.status() or {})
        except Exception:
            tool_status = {}

        node_snapshot: dict[str, Any] = {}
        snapshot = getattr(self.node_registry, "snapshot", None)
        if callable(snapshot):
            try:
                node_snapshot = dict(snapshot() or {})
            except Exception:
                node_snapshot = {}

        live_nodes: list[dict[str, Any]] = []
        capability_names: set[str] = set()
        execution_ready: set[str] = set()
        for raw_node in list(node_snapshot.get("nodes") or [])[:32]:
            if not isinstance(raw_node, dict) or not bool(raw_node.get("connected")):
                continue
            caps = raw_node.get("capabilities")
            if not isinstance(caps, dict):
                caps = {}
            compact_caps: list[dict[str, Any]] = []
            for raw_name, raw_cap in list(caps.items())[:64]:
                name = str(raw_name or "").strip().lower()
                if not name:
                    continue
                cap = dict(raw_cap) if isinstance(raw_cap, dict) else {}
                available = bool(cap.get("available", True))
                readiness = str(cap.get("readiness") or ("ready" if available else "unavailable"))
                metadata = dict(cap.get("metadata") or {}) if isinstance(cap.get("metadata"), dict) else {}
                authorized = metadata.get("execution_authorized") is True
                if available and readiness != "unavailable":
                    capability_names.add(name)
                if available and readiness == "ready" and authorized:
                    execution_ready.add(name)
                compact_caps.append({
                    "name": name,
                    "available": available,
                    "readiness": readiness,
                    "execution_authorized": authorized,
                })
            live_nodes.append({
                "node_id": str(raw_node.get("node_id") or "")[:120],
                "display_name": str(raw_node.get("display_name") or raw_node.get("node_id") or "")[:120],
                "platform": str(raw_node.get("platform") or "")[:80],
                "capabilities": compact_caps,
            })

        connected_node_ids = [
            str(item.get("node_id") or "")
            for item in live_nodes
            if str(item.get("node_id") or "")
        ]

        competence_status: dict[str, Any] = {}
        competence_owner = getattr(self, "competence", None)
        status_fn = getattr(competence_owner, "status", None)
        if callable(status_fn):
            try:
                competence_status = dict(status_fn() or {})
            except Exception:
                competence_status = {}

        demonstrated: dict[str, list[dict[str, Any]]] = {}
        historical_demonstrated: dict[str, list[dict[str, Any]]] = {}
        known_competence_capabilities: set[str] = set()
        find_competence = getattr(competence_owner, "find", None)
        if callable(find_competence):
            try:
                known_competence_capabilities = {
                    str(getattr(item, "capability", "") or "")
                    for item in list(find_competence(limit=500) or [])
                    if str(getattr(item, "capability", "") or "")
                }
            except Exception:
                known_competence_capabilities = set()

        summary_fn = getattr(competence_owner, "summary_for", None)
        if callable(summary_fn):
            for capability in sorted(capability_names | known_competence_capabilities)[:64]:
                try:
                    historical_rows = list(summary_fn(
                        capability,
                        node_ids=(),
                        limit=4,
                    ) or [])
                except Exception:
                    historical_rows = []
                try:
                    rows = list(summary_fn(
                        capability,
                        node_ids=connected_node_ids,
                        limit=4,
                    ) or []) if capability in capability_names else []
                except Exception:
                    rows = []
                if historical_rows:
                    historical_demonstrated[capability] = [
                        {
                            "node_id": str(item.get("node_id") or "")[:120],
                            "skill_id": str(item.get("skill_id") or "")[:180],
                            "implementation_fingerprint": str(
                                item.get("implementation_fingerprint") or ""
                            )[:64],
                            "attempts": int(item.get("attempts") or 0),
                            "verified_successes": int(item.get("verified_successes") or 0),
                            "reliability": float(item.get("reliability") or 0.0),
                            "evidence_strength": float(item.get("evidence_strength") or 0.0),
                            "mean_latency_ms": item.get("mean_latency_ms"),
                            "last_success": item.get("last_success"),
                            "last_observed_at": str(item.get("last_observed_at") or "")[:80],
                        }
                        for item in historical_rows[:4]
                        if isinstance(item, dict)
                    ]
                if rows:
                    demonstrated[capability] = [
                        {
                            "node_id": str(item.get("node_id") or "")[:120],
                            "skill_id": str(item.get("skill_id") or "")[:180],
                            "implementation_fingerprint": str(
                                item.get("implementation_fingerprint") or ""
                            )[:64],
                            "attempts": int(item.get("attempts") or 0),
                            "verified_successes": int(item.get("verified_successes") or 0),
                            "reliability": float(item.get("reliability") or 0.0),
                            "evidence_strength": float(item.get("evidence_strength") or 0.0),
                            "mean_latency_ms": item.get("mean_latency_ms"),
                            "last_success": item.get("last_success"),
                            "last_observed_at": str(item.get("last_observed_at") or "")[:80],
                        }
                        for item in rows[:4]
                        if isinstance(item, dict)
                    ]

        def safe_status(owner: Any) -> dict[str, Any]:
            fn = getattr(owner, "status", None)
            if not callable(fn):
                return {}
            try:
                return dict(fn() or {})
            except Exception:
                return {}

        knowledge_owner = getattr(self, "knowledge_fabric", None)
        knowledge_status = safe_status(knowledge_owner)
        knowledge_substrate: dict[str, Any] = {}
        substrate_fn = getattr(knowledge_owner, "substrate_profile", None)
        if callable(substrate_fn):
            try:
                knowledge_substrate = dict(substrate_fn() or {})
            except Exception:
                knowledge_substrate = {}
        knowledge_evaluation: dict[str, Any] = {}
        evaluation_owner = getattr(self, "knowledge_evaluation_evidence", None)
        evaluation_snapshot = getattr(evaluation_owner, "snapshot", None)
        if callable(evaluation_snapshot):
            try:
                from mary.knowledge import knowledge_substrate_fingerprint
                current_fingerprint = (
                    knowledge_substrate_fingerprint(knowledge_owner)
                    if knowledge_owner is not None
                    else ""
                )
                knowledge_evaluation = dict(
                    evaluation_snapshot(
                        current_substrate_fingerprint=current_fingerprint
                    ) or {}
                )
            except Exception:
                knowledge_evaluation = {}
        procedural_owner = getattr(self, "procedural_skills", None)
        skills_status = safe_status(procedural_owner)
        revision_lineage: dict[str, Any] = {}
        lineage_fn = getattr(procedural_owner, "revision_lineage", None)
        if callable(lineage_fn):
            try:
                revision_lineage = dict(lineage_fn(limit=100) or {})
            except Exception:
                revision_lineage = {}
        world_status = safe_status(getattr(self, "world_model", None))

        revision_rows: list[dict[str, Any]] = []
        revision_fn = getattr(procedural_owner, "revision_queue", None)
        if callable(revision_fn):
            try:
                revision_rows = [
                    dict(item)
                    for item in list(revision_fn(limit=200) or [])
                    if isinstance(item, dict)
                ]
            except Exception:
                revision_rows = []
        revision_by_skill = {
            str(item.get("skill_id") or ""): item
            for item in revision_rows
            if str(item.get("skill_id") or "")
        }

        procedure_rows: list[dict[str, Any]] = []
        approved_fn = getattr(procedural_owner, "approved", None)
        skill_summary_fn = getattr(competence_owner, "skill_summary", None)
        if callable(approved_fn):
            try:
                approved_skills = list(approved_fn() or [])[:64]
            except Exception:
                approved_skills = []
            for skill in approved_skills:
                skill_id = str(getattr(skill, "id", "") or "")[:180]
                if not skill_id:
                    continue
                required_capabilities = [
                    str(item)[:160]
                    for item in list(
                        getattr(skill, "required_capabilities", ()) or ()
                    )[:8]
                    if str(item)
                ]
                primary_capability = (
                    required_capabilities[0]
                    if len(required_capabilities) == 1
                    else ""
                )
                competence_view: dict[str, Any] = {}
                if callable(skill_summary_fn):
                    try:
                        competence_view = dict(skill_summary_fn(
                            skill_id,
                            capability=primary_capability,
                            node_ids=(),
                        ) or {})
                    except Exception:
                        competence_view = {}

                attempts = int(competence_view.get("attempts") or 0)
                verified_successes = int(
                    competence_view.get("verified_successes") or 0
                )
                evidence_strength = float(
                    competence_view.get("evidence_strength") or 0.0
                )
                demonstrated_skill = bool(
                    competence_view.get("demonstrated")
                )
                pressure_row = revision_by_skill.get(skill_id, {})
                revision_pressure = float(
                    pressure_row.get("revision_pressure") or 0.0
                )
                evidence_needed: list[str] = []
                if attempts == 0:
                    evidence_needed.append(
                        "bounded typed terminal outcome for this approved procedure"
                    )
                elif verified_successes == 0:
                    evidence_needed.append(
                        "at least one verified successful terminal outcome"
                    )
                if attempts < 4 or evidence_strength < 0.35:
                    evidence_needed.append(
                        "additional independent outcomes to strengthen competence confidence"
                    )
                if revision_pressure > 0.0:
                    evidence_needed.append(
                        "creator review of failure evidence before any replacement procedure is approved"
                    )

                procedure_rows.append({
                    "skill_id": skill_id,
                    "name": str(getattr(skill, "name", "") or "")[:240],
                    "version": int(getattr(skill, "version", 0) or 0),
                    "required_capabilities": required_capabilities,
                    "state": (
                        "degrading"
                        if revision_pressure > 0.0
                        else (
                            "demonstrated"
                            if demonstrated_skill
                            else (
                                "observed_unverified"
                                if attempts > 0
                                else "approved_untested"
                            )
                        )
                    ),
                    "demonstrated": demonstrated_skill,
                    "degrading": bool(revision_pressure > 0.0),
                    "revision_pressure": revision_pressure,
                    "attempts": attempts,
                    "successes": int(competence_view.get("successes") or 0),
                    "failures": int(competence_view.get("failures") or 0),
                    "verified_successes": verified_successes,
                    "reliability": float(
                        competence_view.get("reliability") or 0.5
                    ),
                    "evidence_strength": evidence_strength,
                    "last_success": competence_view.get("last_success"),
                    "last_observed_at": str(
                        competence_view.get("last_observed_at") or ""
                    )[:80],
                    "evidence_needed": evidence_needed,
                })

        procedure_rows.sort(
            key=lambda item: (
                bool(item.get("degrading")),
                float(item.get("revision_pressure") or 0.0),
                bool(item.get("demonstrated")),
                float(item.get("evidence_strength") or 0.0),
            ),
            reverse=True,
        )

        capability_improvement: dict[str, dict[str, Any]] = {}
        for capability in sorted(capability_names | known_competence_capabilities)[:64]:
            rows = list(historical_demonstrated.get(capability) or [])
            attempts = sum(int(item.get("attempts") or 0) for item in rows)
            verified_successes = sum(
                int(item.get("verified_successes") or 0) for item in rows
            )
            strongest_evidence = max(
                [float(item.get("evidence_strength") or 0.0) for item in rows]
                or [0.0]
            )
            evidence_needed: list[str] = []
            if not rows:
                evidence_needed.append(
                    "a bounded typed task with a terminal outcome on a connected node"
                )
            elif verified_successes == 0:
                evidence_needed.append(
                    "at least one verified successful terminal outcome"
                )
            if attempts < 4 or strongest_evidence < 0.35:
                evidence_needed.append(
                    "additional independent outcomes to strengthen the competence estimate"
                )
            degrading_for_capability = [
                item["skill_id"]
                for item in procedure_rows
                if capability in list(item.get("required_capabilities") or [])
                and bool(item.get("degrading"))
            ]
            if degrading_for_capability:
                evidence_needed.append(
                    "creator-reviewed comparison of a revision candidate against the failing procedure"
                )
            capability_improvement[capability] = {
                "demonstrated": bool(rows and verified_successes > 0),
                "attempts": attempts,
                "verified_successes": verified_successes,
                "strongest_evidence_strength": round(strongest_evidence, 4),
                "degrading_procedure_ids": degrading_for_capability[:12],
                "evidence_needed": evidence_needed,
                "currently_advertised": capability in capability_names,
                "currently_available": capability in capability_names,
                "execution_authorized": capability in execution_ready,
                "authority": (
                    "evidence guidance only; permission and execution remain separate"
                ),
            }

        experiment_snapshot: dict[str, Any] = {}
        experiment_owner = getattr(self, "model_experiments", None)
        experiment_snapshot_fn = getattr(experiment_owner, "snapshot", None)
        if callable(experiment_snapshot_fn):
            try:
                experiment_snapshot = dict(experiment_snapshot_fn() or {})
            except Exception:
                experiment_snapshot = {}
        experiment_records = [
            dict(item)
            for item in list(experiment_snapshot.get("records") or [])[-12:]
            if isinstance(item, dict)
        ]
        experiment_statuses = [
            str(item.get("status") or "").strip().casefold()
            for item in experiment_records
        ]
        experiment_views: list[dict[str, Any]] = []
        for item in experiment_records[-8:]:
            missing_scores = [
                str(value)[:80]
                for value in list(item.get("missing_scores") or [])[:12]
                if str(value)
            ]
            failed_scores = [
                str(value)[:80]
                for value in list(item.get("failed_scores") or [])[:12]
                if str(value)
            ]
            status = str(item.get("status") or "")[:80]
            benchmark_verified = bool(item.get("benchmark_verified"))
            trial_ready = bool(item.get("trial_ready"))
            trial_evidence = (
                dict(item.get("trial_evidence") or {})
                if isinstance(item.get("trial_evidence"), dict)
                else {}
            )
            trial_attempts = int(trial_evidence.get("attempts") or 0)
            completed_trials = int(trial_evidence.get("completed") or 0)
            failed_trials = int(trial_evidence.get("failed") or 0)
            rejected_trials = int(trial_evidence.get("rejected") or 0)
            expired_trials = int(trial_evidence.get("expired") or 0)
            evidence_needed: list[str] = []
            if missing_scores:
                evidence_needed.append(
                    "creator-reviewed semantic scores for: "
                    + ", ".join(missing_scores)
                )
            if failed_scores:
                evidence_needed.append(
                    "improved result and held-out retest for failed dimensions: "
                    + ", ".join(failed_scores)
                )
            if status == "benchmark_mismatch":
                evidence_needed.append(
                    "rerun against the exact pinned MaryBench fingerprint and case count"
                )
            elif not benchmark_verified:
                evidence_needed.append(
                    "exact held-out MaryBench benchmark lineage for this artifact"
                )
            if not trial_ready:
                evidence_needed.append(
                    "all semantic score floors plus exact artifact, dataset, bundle and node benchmark matches"
                )
            elif completed_trials > 0:
                evidence_needed.append(
                    "creator-reviewed comparison of completed bounded trial results before any production-routing decision"
                )
            elif trial_attempts > 0:
                evidence_needed.append(
                    "a completed bounded trial on the exact authorized experiment node before any production-routing decision"
                )
            else:
                evidence_needed.append(
                    "bounded explicit trial outcomes before any production-routing decision"
                )
            experiment_views.append({
                "id": str(item.get("id") or "")[:160],
                "candidate_id": str(item.get("candidate_id") or "")[:160],
                "status": status,
                "runtime": str(item.get("runtime") or "")[:80],
                "model": str(item.get("model") or "")[:240],
                "node_id": str(item.get("node_id") or "")[:160],
                "benchmark_verified": benchmark_verified,
                "trial_ready": trial_ready,
                "mary_fit": item.get("mary_fit"),
                "missing_scores": missing_scores,
                "failed_scores": failed_scores,
                "trial_evidence": {
                    "attempts": trial_attempts,
                    "completed": completed_trials,
                    "failed": failed_trials,
                    "rejected": rejected_trials,
                    "expired": expired_trials,
                    "completed_trial_observed": completed_trials > 0,
                    "latest_status": str(trial_evidence.get("latest_status") or "")[:40],
                    "last_observed_at": str(trial_evidence.get("last_observed_at") or "")[:80],
                    "quality_verified": False,
                    "authority": "content_free_trial_evidence_only",
                },
                "experimental": True,
                "production_authority": False,
                "evidence_needed": evidence_needed,
            })

        experiment_view = {
            "count": int(
                experiment_snapshot.get("count", len(experiment_records)) or 0
            ),
            "reviewed_only": sum(
                1 for status in experiment_statuses if status == "reviewed"
            ),
            "benchmarked": sum(
                1 for status in experiment_statuses if status == "benchmarked"
            ),
            "benchmark_mismatch": sum(
                1
                for status in experiment_statuses
                if status == "benchmark_mismatch"
            ),
            "benchmark_verified": sum(
                1
                for item in experiment_records
                if bool(item.get("benchmark_verified"))
            ),
            "trial_ready": int(experiment_snapshot.get("trial_ready") or 0),
            "trial_outcomes": int(experiment_snapshot.get("trial_outcomes") or 0),
            "completed_trials": int(experiment_snapshot.get("completed_trials") or 0),
            "experimental_records": len(experiment_views),
            "records": experiment_views,
            "training_readiness_claimed": False,
            "automatic_training": False,
            "automatic_promotion": False,
            "authority": "experiment_evidence_only",
        }

        web_search = bool(tool_status.get("web_search_configured"))
        repository_map = dict(tool_status.get("repository_map") or {})
        facts = {
            "core_self_inspection": True,
            "web_search": {
                "available": web_search,
                "provider": str(tool_status.get("web_search_provider") or "")[:120],
            },
            "workspace": {
                "available": bool(tool_status.get("workspace_root")),
                "root_present": bool(tool_status.get("workspace_root")),
            },
            "repository_map": {
                "registered": bool(repository_map.get("registered")),
                "execution": bool(repository_map.get("execution")),
                "mutation": bool(repository_map.get("mutation")),
            },
            "nodes": {
                "connected": len(live_nodes),
                "registered": int(node_snapshot.get("registered") or len(node_snapshot.get("nodes") or [])),
                "live": live_nodes,
                "advertised_capabilities": sorted(capability_names),
                "execution_ready_capabilities": sorted(execution_ready),
                "demonstrated_competence": demonstrated,
                "historical_demonstrated_competence": historical_demonstrated,
                "known_competence_capabilities": sorted(known_competence_capabilities)[:64],
                "competence_records": int(competence_status.get("records") or 0),
            },
            "knowledge_substrate": {
                "packs": int(knowledge_status.get("packs") or 0),
                "enabled": int(knowledge_status.get("enabled") or 0),
                "indexed_documents": int(knowledge_status.get("indexed_documents") or 0),
                "available": bool(
                    int(knowledge_status.get("enabled") or 0)
                    or int(knowledge_status.get("indexed_documents") or 0)
                ),
                "tiers": dict(knowledge_substrate.get("counts") or {}),
                "enabled_retrieval_modes": list(
                    knowledge_substrate.get("enabled_retrieval_modes") or []
                )[:12],
                "attention_required": bool(
                    knowledge_substrate.get("attention_required")
                ),
                "stale_derivatives": len(
                    list(knowledge_substrate.get("stale_derivatives") or [])
                ),
                "stale_local_indexes": len(
                    list(knowledge_substrate.get("stale_local_indexes") or [])
                ),
                "evaluation_runs": int(knowledge_evaluation.get("runs") or 0),
                "latest_evaluation_passed": bool(
                    knowledge_evaluation.get("latest_all_passed")
                ),
                "evaluation_stale": bool(knowledge_evaluation.get("stale")),
                "evaluation_current_substrate_match": bool(
                    knowledge_evaluation.get("current_substrate_match")
                ),
                "evaluation_content_retained": bool(
                    knowledge_evaluation.get("content_retained", False)
                ),
            },
            "procedural_memory": {
                "approved": int(skills_status.get("approved") or 0),
                "candidates": int(skills_status.get("candidates") or 0),
                "revision_attention": int(skills_status.get("revision_attention") or 0),
                "revision_lineage": revision_lineage,
                "demonstrated": sum(
                    1 for item in procedure_rows
                    if bool(item.get("demonstrated"))
                ),
                "degrading": sum(
                    1 for item in procedure_rows
                    if bool(item.get("degrading"))
                ),
                "procedures": procedure_rows[:16],
            },
            "capability_improvement": capability_improvement,
            "world_model": {
                "current_beliefs": int(world_status.get("current_beliefs") or 0),
                "reconciliation_groups": int(world_status.get("reconciliation_groups") or 0),
            },
            "model_experiments": experiment_view,
        }

        if web_search:
            search_sentence = "Web search is configured through my registered tool layer."
        else:
            search_sentence = "Web search is not currently configured in my registered tool layer."
        if live_nodes:
            node_sentence = (
                f"I currently have {len(live_nodes)} connected capability node"
                f"{'s' if len(live_nodes) != 1 else ''}; I should use only the capabilities "
                "they actually advertise and still respect their execution permissions."
            )
        else:
            node_sentence = "I do not currently have a connected capability node to claim device execution from."

        lowered_query = str(query or "").casefold()
        requested_groups: list[tuple[str, tuple[str, ...]]] = []
        if any(term in lowered_query for term in ("screen", "desktop view", "see my app", "see the app")):
            requested_groups.append(("screen vision", ("sensor.screen_describe",)))
        if any(term in lowered_query for term in ("image", "picture", "photo")):
            requested_groups.append(("image vision", ("sensor.image_describe",)))
        if any(term in lowered_query for term in ("hear", "microphone", "audio", "transcribe", "listen")):
            requested_groups.append((
                "audio transcription",
                ("sensor.audio_transcribe", "audio.transcribe"),
            ))
        if any(term in lowered_query for term in ("local model", "local llm", "ollama", "llama.cpp", "mlx")):
            requested_groups.append((
                "local model inference",
                ("llm.local", "llm.ollama", "llm.llama_cpp", "llm.mlx_lm"),
            ))
        asks_local_knowledge = any(
            term in lowered_query
            for term in ("local knowledge", "knowledge search", "corpus", "offline library")
        )
        asks_procedure_evidence = any(
            term in lowered_query
            for term in (
                "procedure",
                "procedural",
                "skill",
                "learned",
                "good at",
                "demonstrated",
                "degrading",
                "improve",
                "improvement evidence",
                "evidence do you need",
            )
        )
        asks_model_experiments = any(
            term in lowered_query
            for term in (
                "lora",
                "adapter",
                "model experiment",
                "model lab",
                "marybench",
                "benchmark",
                "fine tune",
                "fine-tune",
                "training ready",
                "train mary",
                "trial ready",
                "trial-ready",
            )
        )
        if any(term in lowered_query for term in ("web", "browse", "internet")):
            requested_groups.append(("web search", ()))

        requested_sentences: list[str] = []
        if any(
            term in lowered_query
            for term in (
                "what can you do",
                "your capabilities",
                "your tools",
                "your nodes",
                "capability nodes",
                "nodes actually do",
            )
        ):
            advertised_summary = ", ".join(sorted(capability_names)[:16])
            authorized_summary = ", ".join(sorted(execution_ready)[:16])
            if advertised_summary:
                requested_sentences.append(
                    "My connected nodes currently advertise: "
                    + advertised_summary
                    + "."
                )
            else:
                requested_sentences.append(
                    "No connected node currently advertises a device capability."
                )
            if authorized_summary:
                requested_sentences.append(
                    "The currently execution-authorized ready subset is: "
                    + authorized_summary
                    + "."
                )
            elif advertised_summary:
                requested_sentences.append(
                    "None of those advertised node capabilities is currently both ready "
                    "and execution-authorized."
                )

        if asks_local_knowledge:
            local_state = facts["knowledge_substrate"]
            modes = ", ".join(local_state["enabled_retrieval_modes"])
            stale_local = int(local_state["stale_local_indexes"])
            stale_semantic = int(local_state["stale_derivatives"])
            knowledge_node_represented = "knowledge.search" in capability_names
            knowledge_node_ready = "knowledge.search" in execution_ready

            if local_state["available"]:
                sentence = "My local knowledge substrate is available"
                if modes:
                    sentence += f" through {modes}"
                sentence += "."
                if stale_local:
                    sentence += (
                        f" {stale_local} local index"
                        f"{'es' if stale_local != 1 else ''} "
                        "is stale and needs explicit reindexing before I should describe "
                        "all local retrieval as current."
                    )
                if stale_semantic:
                    sentence += (
                        f" {stale_semantic} semantic derivative"
                        f"{'s' if stale_semantic != 1 else ''} "
                        "also needs refresh/review."
                    )
                if knowledge_node_ready:
                    sentence += (
                        " A connected knowledge.search node is also ready and "
                        "execution-authorized."
                    )
                elif knowledge_node_represented:
                    sentence += (
                        " A connected knowledge.search node is advertised, but it is "
                        "not presently execution-authorized."
                    )
                requested_sentences.append(sentence)
            elif knowledge_node_ready:
                requested_sentences.append(
                    "My Core local knowledge substrate is not currently available, "
                    "but a connected knowledge.search node is ready and execution-authorized."
                )
            elif knowledge_node_represented:
                requested_sentences.append(
                    "My Core local knowledge substrate is not currently available. "
                    "A connected knowledge.search node is advertised, but it is not "
                    "presently execution-authorized."
                )
            else:
                requested_sentences.append(
                    "I do not currently have an available Core local knowledge substrate "
                    "or a connected knowledge.search route to claim."
                )

        if asks_procedure_evidence:
            procedure_state = facts["procedural_memory"]
            demonstrated_count = int(procedure_state.get("demonstrated") or 0)
            degrading_count = int(procedure_state.get("degrading") or 0)
            requested_sentences.append(
                "My approved procedures and demonstrated competence are separate evidence layers. "
                f"I currently project {demonstrated_count} approved procedure"
                f"{'s' if demonstrated_count != 1 else ''} with verified successful evidence "
                f"and {degrading_count} procedure"
                f"{'s' if degrading_count != 1 else ''} under degradation/revision review. "
                "Plans may rank demonstrated approved procedures more highly, but competence "
                "never approves, binds, authorizes, or executes a procedure by itself."
            )
            missing = [
                item
                for item in list(procedure_state.get("procedures") or [])
                if list(item.get("evidence_needed") or [])
            ][:3]
            if missing:
                requested_sentences.append(
                    "The highest-priority procedure evidence gaps are: "
                    + "; ".join(
                        f"{str(item.get('name') or item.get('skill_id') or 'procedure')}: "
                        + ", ".join(list(item.get("evidence_needed") or [])[:2])
                        for item in missing
                    )
                    + "."
                )

        if asks_model_experiments:
            model_state = facts["model_experiments"]
            if model_state["count"]:
                requested_sentences.append(
                    "My model lab currently has "
                    f"{model_state['count']} reviewed experiment record"
                    f"{'s' if model_state['count'] != 1 else ''}, "
                    f"{model_state['benchmark_verified']} with verified benchmark lineage, "
                    f"and {model_state['trial_ready']} trial-ready. "
                    "Trial-ready means an exact reviewed artifact has enough held-out "
                    "evidence for an explicit bounded experiment; it does not mean "
                    "production promotion. The experiment ledger does not establish "
                    "MLX training readiness by itself—prepared-bundle and host/package "
                    "preflight remain separate local gates, and training is never automatic."
                )
            else:
                requested_sentences.append(
                    "I do not currently have a reviewed model/adapter experiment in my "
                    "Core experiment ledger. Training and promotion are not automatic, "
                    "and I should not claim an adapter is ready without exact bundle, "
                    "host/preflight, benchmark, and creator-review evidence."
                )

        for label, names in requested_groups[:6]:
            if label == "web search":
                if web_search:
                    requested_sentences.append(
                        "Web search is configured in my registered tool layer."
                    )
                else:
                    requested_sentences.append(
                        "Web search is not currently configured in my registered tool layer."
                    )
                continue
            represented = [name for name in names if name in capability_names]
            ready = [name for name in represented if name in execution_ready]
            if ready:
                requested_sentences.append(
                    f"My connected nodes currently advertise and execution-authorize {label} "
                    f"through {', '.join(ready)}."
                )
            elif represented:
                requested_sentences.append(
                    f"My connected nodes currently advertise {label} through "
                    f"{', '.join(represented)}, but it is not presently execution-authorized."
                )
            else:
                requested_sentences.append(
                    f"No connected node currently advertises {label}, so I should not claim "
                    "I can execute it right now."
                )

        capability_answer = " ".join(requested_sentences)
        if capability_answer:
            capability_answer += " "

        return {
            "agency_status": self.agency.status(),
            "tool_status": tool_status,
            "live_capabilities": facts,
            "autonomy_type": type(self.autonomy).__name__,
            "authority": (
                "live Core/tool/node state plus bounded competence/knowledge/procedure/model-experiment evidence "
                "is authoritative for capability claims; provider model priors are not capability evidence"
            ),
            "fallback_response": (
                capability_answer
                + "I can inspect my own Core/runtime state and analyze problems directly. "
                + search_sentence + " " + node_sentence + " "
                "A capability being present is separate from permission to execute it, and "
                "advertised capability is separate from demonstrated competence. "
                "I cannot silently rewrite or redeploy myself, and I should never claim "
                "a tool, device action, browse, file, vision, voice, or model capability "
                "unless the live capability graph says it is available."
            ),
        }
