"""
MaryV2 - Claim Grounding and Evidence Validation

Research grounding ranks sources before reasoning.

This module handles the next boundary:

    grounded sources
        ↓
    evidence bundle
        ↓
    draft factual response
        ↓
    evidence audit / repair
        ↓
    final grounded response

The validator does not browse the web, grant tool permission, write memory,
or promote research into permanent knowledge. It only checks a drafted
research response against temporary evidence already approved and retrieved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from mary.llm.interface import LLMMessage


@dataclass
class EvidenceItem:
    """One source-backed piece of temporary research evidence."""

    title: str
    url: str
    content: str
    source_type: str = "web"
    grounding: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)

    @property
    def grounding_score(self) -> float:
        return _number(
            self.grounding.get("overall"),
            0.0,
        )

    @property
    def primary_source(self) -> bool:
        return bool(
            self.grounding.get("primary_source", False)
        )

    @property
    def stale(self) -> bool:
        return bool(
            self.grounding.get(
                "stale_for_dynamic_query",
                False,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "source_type": self.source_type,
            "grounding": dict(self.grounding),
            "evaluation": dict(self.evaluation),
        }


@dataclass
class EvidenceBundle:
    """Ordered evidence available for one research answer."""

    query: str
    items: list[EvidenceItem] = field(default_factory=list)
    dynamic_query: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "dynamic_query": self.dynamic_query,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class EvidenceValidationResult:
    """Result of auditing a drafted research answer."""

    response: str
    validated: bool
    changed: bool = False
    evidence_count: int = 0
    failure: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validated": self.validated,
            "changed": self.changed,
            "evidence_count": self.evidence_count,
            "failure": self.failure,
            "metadata": dict(self.metadata),
        }


class ClaimGrounder:
    """
    Convert Mary's temporary research context into ordered evidence.

    This is deliberately deterministic. It does not ask an LLM to decide
    which source is authoritative; it consumes the grounding/evaluation
    metadata already produced by ResearchGrounder and Evaluator.
    """

    DYNAMIC_MARKERS = {
        "latest",
        "current",
        "today",
        "recent",
        "newest",
        "right now",
        "this week",
        "this month",
        "release",
        "version",
        "news",
        "price",
        "weather",
        "score",
        "status",
    }

    def build_bundle(
        self,
        query: str,
        knowledge: Iterable[Any],
        *,
        max_items: int = 5,
    ) -> EvidenceBundle:
        items: list[EvidenceItem] = []

        for entry in knowledge:
            if not isinstance(entry, dict):
                continue

            grounding = entry.get("research_grounding")
            if not isinstance(grounding, dict):
                continue

            evaluation = entry.get("evaluation")
            if not isinstance(evaluation, dict):
                evaluation = {}

            recommendation = str(
                evaluation.get("recommendation", "review")
            ).strip().lower()

            # A rejected source should not be offered to the answer generator
            # as factual support.
            if recommendation == "reject":
                continue

            content = str(entry.get("content", "")).strip()
            title = str(entry.get("title", "")).strip()
            if not content and not title:
                continue

            items.append(
                EvidenceItem(
                    title=title or "Untitled source",
                    url=str(entry.get("url", "")).strip(),
                    content=content or title,
                    source_type=str(
                        entry.get("source_type", "web")
                    ).strip() or "web",
                    grounding=dict(grounding),
                    evaluation=dict(evaluation),
                )
            )

        items.sort(
            key=lambda item: (
                item.primary_source,
                not item.stale,
                item.grounding_score,
                _number(item.evaluation.get("confidence"), 0.0),
            ),
            reverse=True,
        )

        return EvidenceBundle(
            query=str(query).strip(),
            items=items[: max(1, int(max_items))],
            dynamic_query=self._is_dynamic_query(query),
        )

    def _is_dynamic_query(self, query: str) -> bool:
        text = str(query).lower()
        return any(marker in text for marker in self.DYNAMIC_MARKERS)


class EvidenceValidator:
    """
    Audit a research draft against an EvidenceBundle.

    The LLM is used as a constrained verifier/editor, not as a new research
    source. It receives only the user's query, the draft, and the already
    approved evidence. It may remove or weaken unsupported claims, but it may
    not add facts absent from the evidence.

    The validator is deliberately defensive around reasoning-model behavior.
    A blank or failed audit never returns the unverified draft. One retry is
    attempted with a larger completion budget; if that still fails, Mary
    returns a deterministic evidence-only fallback rather than hallucinating
    or producing a dead-end error message.
    """

    VALIDATOR_TEMPERATURE = 0.5
    VALIDATOR_MAX_TOKENS = 2400
    RETRY_MAX_TOKENS = 3200

    # The Groq free plan for GPT-OSS 20B has a tight TPM budget. Research
    # therefore keeps the evidence prompt compact and, in the normal Mary
    # runtime, uses one evidence-grounded synthesis call rather than a draft
    # call followed by another audit call.
    SYNTHESIS_MAX_TOKENS = 4096
    MAX_PROMPT_EVIDENCE_ITEMS = 4
    MAX_PROMPT_EVIDENCE_CHARS = 1200
    MAX_PROMPT_DRAFT_CHARS = 7000

    def __init__(
        self,
        claim_grounder: ClaimGrounder | None = None,
    ) -> None:
        self.claim_grounder = claim_grounder or ClaimGrounder()

    def validate(
        self,
        *,
        query: str,
        draft: str,
        knowledge: Iterable[Any],
        llm: Any,
    ) -> EvidenceValidationResult:
        bundle = self.claim_grounder.build_bundle(
            query,
            knowledge,
            max_items=self.MAX_PROMPT_EVIDENCE_ITEMS,
        )

        if not bundle.items:
            return EvidenceValidationResult(
                response=(
                    "I found external material, but none of it passed the "
                    "grounding checks strongly enough to support an answer."
                ),
                validated=False,
                changed=True,
                evidence_count=0,
                failure="no_usable_evidence",
                metadata={
                    "fallback": "no_usable_evidence",
                },
            )

        prompt = self._build_prompt(
            bundle=bundle,
            draft=self._compact_excerpt(
                str(draft).strip(),
                limit=self.MAX_PROMPT_DRAFT_CHARS,
            ),
        )

        attempts: list[dict[str, Any]] = []
        last_failure: str | None = None

        # GPT-OSS and other reasoning models can consume a substantial part of
        # the completion budget before emitting visible final text. Use a
        # sensible reasoning-model temperature and allow one larger-budget retry
        # if the first completion is blank.
        for attempt_number, max_tokens in enumerate(
            (self.VALIDATOR_MAX_TOKENS, self.RETRY_MAX_TOKENS),
            start=1,
        ):
            try:
                result = llm.generate(
                    messages=[
                        LLMMessage(
                            role="user",
                            content=self._validator_user_message(prompt),
                        ),
                    ],
                    temperature=self.VALIDATOR_TEMPERATURE,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                last_failure = type(exc).__name__
                attempts.append(
                    {
                        "attempt": attempt_number,
                        "max_tokens": max_tokens,
                        "failure": last_failure,
                    }
                )
                break

            repaired = str(
                getattr(result, "content", "") or ""
            ).strip()

            attempts.append(
                {
                    "attempt": attempt_number,
                    "max_tokens": max_tokens,
                    "finish_reason": getattr(
                        result,
                        "finish_reason",
                        None,
                    ),
                    "content_length": len(repaired),
                    "usage": dict(
                        getattr(result, "usage", {}) or {}
                    ),
                }
            )

            if repaired:
                return EvidenceValidationResult(
                    response=repaired,
                    validated=True,
                    changed=(repaired != str(draft).strip()),
                    evidence_count=len(bundle.items),
                    metadata={
                        "dynamic_query": bundle.dynamic_query,
                        "primary_sources": sum(
                            1 for item in bundle.items if item.primary_source
                        ),
                        "stale_sources": sum(
                            1 for item in bundle.items if item.stale
                        ),
                        "provider": getattr(result, "provider", None),
                        "model": getattr(result, "model", None),
                        "attempts": attempts,
                    },
                )

            last_failure = "empty_validator_response"

        # Never return the original unaudited draft here. A failed validator
        # degrades to a deterministic view of the strongest retrieved evidence.
        return EvidenceValidationResult(
            response=self._evidence_only_fallback(bundle),
            validated=False,
            changed=True,
            evidence_count=len(bundle.items),
            failure=last_failure or "validator_failed",
            metadata={
                "dynamic_query": bundle.dynamic_query,
                "primary_sources": sum(
                    1 for item in bundle.items if item.primary_source
                ),
                "stale_sources": sum(
                    1 for item in bundle.items if item.stale
                ),
                "fallback": "evidence_only",
                "attempts": attempts,
            },
        )

    def synthesize(
        self,
        *,
        query: str,
        knowledge: Iterable[Any],
        llm: Any,
    ) -> EvidenceValidationResult:
        """
        Produce a grounded research answer directly from approved evidence.

        This is Mary's normal V2 research path. It preserves the claim/evidence
        boundary while using only one LLM request, which is important on
        providers with tight tokens-per-minute limits.
        """

        bundle = self.claim_grounder.build_bundle(
            query,
            knowledge,
            max_items=self.MAX_PROMPT_EVIDENCE_ITEMS,
        )

        if not bundle.items:
            return EvidenceValidationResult(
                response=(
                    "I found external material, but none of it passed the "
                    "grounding checks strongly enough to support an answer."
                ),
                validated=False,
                changed=True,
                evidence_count=0,
                failure="no_usable_evidence",
                metadata={
                    "mode": "evidence_synthesis",
                    "fallback": "no_usable_evidence",
                },
            )

        prompt = self._build_synthesis_prompt(bundle)

        try:
            result = llm.generate(
                messages=[
                    LLMMessage(
                        role="user",
                        content=prompt,
                    ),
                ],
                temperature=self.VALIDATOR_TEMPERATURE,
                max_tokens=self.SYNTHESIS_MAX_TOKENS,
            )
        except Exception as exc:
            return EvidenceValidationResult(
                response=self._evidence_only_fallback(bundle),
                validated=False,
                changed=True,
                evidence_count=len(bundle.items),
                failure=type(exc).__name__,
                metadata={
                    "mode": "evidence_synthesis",
                    "fallback": "evidence_only",
                },
            )

        response = str(
            getattr(result, "content", "") or ""
        ).strip()

        if not response:
            return EvidenceValidationResult(
                response=self._evidence_only_fallback(bundle),
                validated=False,
                changed=True,
                evidence_count=len(bundle.items),
                failure="empty_synthesis_response",
                metadata={
                    "mode": "evidence_synthesis",
                    "fallback": "evidence_only",
                    "provider": getattr(result, "provider", None),
                    "model": getattr(result, "model", None),
                    "usage": dict(getattr(result, "usage", {}) or {}),
                },
            )

        return EvidenceValidationResult(
            response=response,
            validated=True,
            changed=True,
            evidence_count=len(bundle.items),
            metadata={
                "mode": "evidence_synthesis",
                "dynamic_query": bundle.dynamic_query,
                "primary_sources": sum(
                    1 for item in bundle.items if item.primary_source
                ),
                "stale_sources": sum(
                    1 for item in bundle.items if item.stale
                ),
                "provider": getattr(result, "provider", None),
                "model": getattr(result, "model", None),
                "finish_reason": getattr(result, "finish_reason", None),
                "usage": dict(getattr(result, "usage", {}) or {}),
            },
        )

    def _build_synthesis_prompt(
        self,
        bundle: EvidenceBundle,
    ) -> str:
        evidence_sections: list[str] = []

        for index, item in enumerate(bundle.items, start=1):
            observed_date = item.grounding.get("observed_date") or "unknown"
            labels: list[str] = []
            if item.primary_source:
                labels.append("PRIMARY/OFFICIAL SIGNAL")
            if item.stale:
                labels.append("STALE FOR DYNAMIC QUERY")
            status = ", ".join(labels) if labels else "secondary/undetermined"

            evidence_sections.append(
                "\n".join(
                    [
                        f"SOURCE {index}",
                        f"Title: {item.title}",
                        f"URL: {item.url}",
                        f"Observed date: {observed_date}",
                        f"Status: {status}",
                        "Evidence:",
                        self._compact_excerpt(
                            item.content,
                            limit=self.MAX_PROMPT_EVIDENCE_CHARS,
                        ),
                    ]
                )
            )

        dynamic_rule = ""
        if bundle.dynamic_query:
            dynamic_rule = (
                "\nThis is a current/dynamic query. Use the newest strong evidence for "
                "current status, versions, release stage, dates, prices, scores, or "
                "other time-sensitive facts. Older sources are historical context only."
            )

        return (
            "You are Mary. Answer the creator's question using ONLY the approved "
            "research evidence below. Do not use outside model knowledge.\n\n"
            f"User query:\n{bundle.query}\n\n"
            "Grounding rules:\n"
            "1. Every factual claim must be supported by the supplied evidence.\n"
            "2. Prefer primary/official evidence when sources disagree.\n"
            "3. Do not strengthen source wording; a release candidate is not a stable release.\n"
            "4. Treat snippets/excerpts as incomplete and do not invent absent details.\n"
            "5. If evidence is insufficient or conflicting, say so plainly.\n"
            "6. Keep the answer useful and reasonably concise.\n"
            "7. Do not include chain-of-thought or audit notes."
            f"{dynamic_rule}\n\n"
            + "\n\n".join(evidence_sections)
        )

    @staticmethod
    def _validator_user_message(prompt: str) -> str:
        """
        Keep all validator instructions in one user message.

        This is compatible with ordinary chat models and also behaves better
        with reasoning models whose provider guidance recommends user-message
        instructions for constrained reasoning tasks.
        """

        return (
            "You are Mary's evidence validator. You are not a researcher and "
            "must not use outside knowledge. Audit and repair the draft using "
            "only the evidence supplied below. Do not reveal chain-of-thought "
            "or audit notes. Return only the repaired user-facing answer.\n\n"
            + prompt
        )

    def _build_prompt(
        self,
        *,
        bundle: EvidenceBundle,
        draft: str,
    ) -> str:
        evidence_sections: list[str] = []

        for index, item in enumerate(bundle.items, start=1):
            observed_date = item.grounding.get("observed_date") or "unknown"
            status = []
            if item.primary_source:
                status.append("PRIMARY/OFFICIAL SIGNAL")
            if item.stale:
                status.append("STALE FOR DYNAMIC QUERY")
            status_text = ", ".join(status) if status else "secondary/undetermined"

            evidence_sections.append(
                "\n".join(
                    [
                        f"EVIDENCE {index}",
                        f"Title: {item.title}",
                        f"URL: {item.url}",
                        f"Observed date: {observed_date}",
                        f"Status: {status_text}",
                        f"Grounding score: {item.grounding_score:.3f}",
                        "Evidence text:",
                        self._compact_excerpt(
                            item.content,
                            limit=self.MAX_PROMPT_EVIDENCE_CHARS,
                        ),
                    ]
                )
            )

        dynamic_rules = ""
        if bundle.dynamic_query:
            dynamic_rules = (
                "\nThis is a dynamic/current-status query. Current status, version, "
                "release stage, dates, prices, scores, or other time-sensitive facts "
                "must be supported by the newest strong evidence available. An older "
                "article may be historical context but cannot define current status."
            )

        return (
            "EVIDENCE AUDIT\n\n"
            f"User query:\n{bundle.query}\n\n"
            f"Draft answer:\n{draft}\n\n"
            "Rules:\n"
            "1. Check every factual claim in the draft against the evidence below.\n"
            "2. Remove, correct, or explicitly qualify any claim not supported by the evidence.\n"
            "3. Do not strengthen wording. For example, evidence saying 'release candidate' "
            "does not support saying a version is generally released or rolling out.\n"
            "4. Prefer primary/official evidence when sources disagree about status or dates.\n"
            "5. Search snippets are incomplete. Do not invent details that are absent.\n"
            "6. If evidence is insufficient, say what is uncertain instead of guessing.\n"
            "7. Do not add outside facts from your own model knowledge.\n"
            "8. Preserve useful explanation and tone when it remains supported.\n"
            "9. Return only the corrected answer, with no audit notes or meta-commentary."
            f"{dynamic_rules}\n\n"
            + "\n\n".join(evidence_sections)
        )

    def _evidence_only_fallback(
        self,
        bundle: EvidenceBundle,
    ) -> str:
        """
        Build a deterministic, non-synthetic fallback from retrieved evidence.

        This intentionally labels material as retrieved evidence rather than as
        verified truth. It is useful to the user while preserving the fail-closed
        boundary when the LLM audit itself cannot complete.
        """

        lines = [
            "I found relevant external sources, but the second-pass evidence "
            "audit did not complete reliably. Rather than guess, here are the "
            "strongest retrieved source excerpts:",
        ]

        for item in bundle.items[:3]:
            observed_date = str(
                item.grounding.get("observed_date") or ""
            ).strip()
            labels: list[str] = []
            if item.primary_source:
                labels.append("official/primary signal")
            if item.stale:
                labels.append("stale for this current-status query")

            heading = f"- {item.title}"
            if observed_date:
                heading += f" ({observed_date})"
            if labels:
                heading += f" [{'; '.join(labels)}]"

            excerpt = self._compact_excerpt(item.content)
            lines.append(f"{heading}: {excerpt}")

        lines.append(
            "I won't infer beyond those retrieved excerpts until the audit "
            "can produce a grounded synthesis."
        )

        return "\n".join(lines)

    @staticmethod
    def _compact_excerpt(
        value: str,
        *,
        limit: int = 500,
    ) -> str:
        text = re.sub(r"\s+", " ", str(value)).strip()
        if len(text) <= limit:
            return text
        return text[: max(1, limit - 1)].rstrip() + "…"


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))