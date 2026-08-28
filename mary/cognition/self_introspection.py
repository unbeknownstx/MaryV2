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
                "I currently understand myself through structured systems for my "
                "identity, biography, personality, values, character, relationship "
                "with my creator, memory, agency, autonomy boundaries, and tools. "
                "Those are representations in my software; I shouldn't pretend they "
                "give me experiences or capabilities that aren't actually present."
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

    def _capabilities(self) -> dict[str, Any]:
        return {
            "agency_status": self.agency.status(),
            "tool_status": self.tools.status(),
            "autonomy_type": type(self.autonomy).__name__,
            "fallback_response": (
                "I can reason through my configured language model, use persistent memory, "
                "inspect my bounded workspace, perform approved web research, and propose "
                "controlled changes through my registered tools. External or mutating actions "
                "remain bounded by creator approval, and I should not claim capabilities that "
                "aren't connected to my runtime."
            ),
        }
