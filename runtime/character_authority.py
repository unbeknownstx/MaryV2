"""Mary Character Authority Alpha runtime adapter.

Low-coupling loader/selector designed to feed the existing MaryV2
`personality_context` / prompt assembly without making providers own identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

_TOKEN_RE = re.compile(r"[a-z0-9']+")

def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text).lower()))

@dataclass
class CharacterSelection:
    core_rules: list[dict[str, Any]]
    contextual_rules: list[dict[str, Any]]
    relationship: dict[str, Any] | None
    exemplars: list[dict[str, Any]]
    anti_patterns: list[dict[str, Any]]

    def as_prompt_payload(self) -> dict[str, Any]:
        return {
            "authority_version": "0.1.0-alpha",
            "rules": [*self.core_rules, *self.contextual_rules],
            "relationship_lens": self.relationship,
            "behavior_exemplars": self.exemplars,
            "anti_patterns": self.anti_patterns,
            "instruction": (
                "Use these as behavioral evidence, not exact wording. Preserve identity/memory "
                "boundaries. Do not force every trait into the response."
            ),
        }

class MaryCharacterAuthority:
    CORE_IDS = {
        "ID-001","ID-002","ID-003","ID-004","ID-006",
        "CORE-001","CORE-003","CORE-005","CORE-006","CORE-010",
        "HUM-001","HUM-007","CARE-001","CARE-004","REL-001",
        "REL-005","REL-008","EMO-007","VOICE-002",
    }

    CUES = {
        "humor":{"joke","funny","laugh","tease","roast","sarcasm","meme","embarrass","stupid","fries"},
        "care":{"sad","cry","hurt","failure","failed","comfort","alone","upset","grief","scared"},
        "intelligence":{"think","research","why","how","evidence","wrong","debate","learn","explain","idea","expert"},
        "work":{"work","job","deadline","project","boss","team","plan","late","finish","task"},
        "relationship":{"friend","trust","love","date","flirt","miss","relationship","together","beautiful"},
        "emotion":{"angry","mad","fear","afraid","embarrassed","excited","tired","exhausted","jealous"},
        "lived_in":{"food","music","game","anime","rain","outfit","clothes","room","cook","draw","art"},
        "identity":{"real","ai","model","mary","fictional","novel","memory","remember","creator","unbe","dave"},
        "voice_bridge":{"voice","sound","tts","elevenlabs","speak","vocal","tone"},
    }

    def __init__(self, package_root: str | Path | None = None) -> None:
        root = Path(package_root) if package_root else Path(__file__).resolve().parents[1]
        data = root / "data"
        self.authority = json.loads((data / "mary_character_authority_alpha.json").read_text(encoding="utf-8"))
        self.relationships = json.loads((data / "mary_relationship_ladder_alpha.json").read_text(encoding="utf-8"))
        self.anti = json.loads((data / "mary_anti_patterns_alpha.json").read_text(encoding="utf-8"))
        self.corpus = [
            json.loads(line)
            for line in (data / "mary_behavior_corpus_alpha.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _categories(self, text: str) -> set[str]:
        words = _tokens(text)
        out = {category for category, cues in self.CUES.items() if words & cues}
        return out or {"temperament"}

    def _rule_score(self, item: dict[str, Any], words: set[str], categories: set[str]) -> float:
        score = float(item.get("strength", 0.5))
        if item.get("category") in categories:
            score += 2.0
        tags = set(map(str.lower, item.get("tags", [])))
        score += 0.45 * len(tags & words)
        return score

    def _relationship(self, relationship_stage: str | None) -> dict[str, Any] | None:
        if not relationship_stage:
            return None
        return next((s for s in self.relationships.get("stages", []) if s.get("id") == relationship_stage), None)

    def select(
        self,
        input_text: str,
        *,
        relationship_stage: str | None = None,
        max_context_rules: int = 10,
        max_exemplars: int = 3,
        max_anti_patterns: int = 4,
    ) -> CharacterSelection:
        words = _tokens(input_text)
        categories = self._categories(input_text)
        all_rules = self.authority["rules"]
        core = [r for r in all_rules if r.get("id") in self.CORE_IDS]
        candidates = [r for r in all_rules if r.get("id") not in self.CORE_IDS]
        candidates.sort(key=lambda r: self._rule_score(r, words, categories), reverse=True)
        contextual = candidates[:max_context_rules]

        def exemplar_score(item: dict[str, Any]) -> float:
            score = float(item.get("strength", 0.5))
            tags = set(map(str.lower, item.get("tags", [])))
            score += 0.55 * len(tags & words)
            if relationship_stage and item.get("relationship") == relationship_stage:
                score += 1.25
            return score

        examples = sorted(self.corpus, key=exemplar_score, reverse=True)[:max_exemplars]

        anti_scored = []
        for item in self.anti.get("patterns", []):
            blob = " ".join([item.get("pattern",""), item.get("why",""), item.get("correction","")])
            overlap = len(_tokens(blob) & words)
            # Assistant-pattern protection is generally useful in Mary chat.
            score = overlap + (0.35 if "assistant" in blob.lower() else 0.0)
            anti_scored.append((score, item))
        anti_scored.sort(key=lambda pair: pair[0], reverse=True)
        anti = [item for _, item in anti_scored[:max_anti_patterns]]

        return CharacterSelection(
            core_rules=core,
            contextual_rules=contextual,
            relationship=self._relationship(relationship_stage),
            exemplars=examples,
            anti_patterns=anti,
        )

    def compile_personality_context(
        self,
        input_text: str,
        *,
        relationship_stage: str | None = None,
    ) -> dict[str, Any]:
        """Bounded payload suitable for the existing MaryV2 `personality_context`."""
        return {
            "character_authority": self.select(
                input_text,
                relationship_stage=relationship_stage,
            ).as_prompt_payload()
        }
