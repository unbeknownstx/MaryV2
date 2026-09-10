"""Cheap Mary behavior-classification interface.

A FastBrain is a replaceable specialist for *small decisions*, not Mary's
identity and not her main conversational brain.  It can be backed by a tiny
local model, an ONNX classifier, or the deterministic baseline below.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Protocol

from mary.runtime.turn_observability import record_turn_stage


@dataclass(frozen=True)
class FastBrainRequest:
    task: str
    text: str
    context: Mapping[str, Any] = field(default_factory=dict)
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class FastBrainResult:
    label: str
    confidence: float
    scores: Mapping[str, float] = field(default_factory=dict)
    provider: str = "deterministic"
    model: str = "rules-v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence"] = round(max(0.0, min(1.0, float(self.confidence))), 3)
        payload["scores"] = {
            str(key): round(max(0.0, min(1.0, float(value))), 3)
            for key, value in dict(self.scores).items()
        }
        return payload


class FastBrainProvider(Protocol):
    def classify(self, request: FastBrainRequest) -> FastBrainResult: ...


class DeterministicFastBrain:
    """Zero-dependency baseline for tests/offline operation."""

    @staticmethod
    def _trace(result: FastBrainResult) -> FastBrainResult:
        record_turn_stage(
            "fast_brain", status="success", elapsed_ms=0.0, outcome=str(result.label)[:64]
        )
        return result

    def classify(self, request: FastBrainRequest) -> FastBrainResult:
        task = str(request.task or "").strip().casefold()
        text = " ".join(str(request.text or "").split()).strip().casefold()
        labels = tuple(str(item) for item in request.labels)

        if task in {"stream_attention", "attention"}:
            direct = any(marker in text for marker in ("mary", "@mary", "hey mary"))
            question = "?" in text
            spam = len(set(text.split())) <= 2 and len(text.split()) >= 5
            score = 0.78 if direct else (0.58 if question else 0.28)
            if spam:
                score *= 0.35
            label = "respond" if score >= 0.68 else ("notice" if score >= 0.46 else "ignore")
            return self._trace(FastBrainResult(label, score, {"respond": score, "ignore": 1.0 - score}))

        if task in {"directed_to", "target"}:
            if "mary" in text or "@mary" in text:
                return self._trace(FastBrainResult("mary", 0.9, {"mary": 0.9}))
            return self._trace(FastBrainResult("general", 0.62, {"general": 0.62}))

        if labels:
            return self._trace(FastBrainResult(labels[0], 0.34, {labels[0]: 0.34}))
        return self._trace(FastBrainResult("unknown", 0.2, {"unknown": 0.2}))


class CallableFastBrain:
    """Adapter for a tiny local model callback without coupling Mary to Ollama."""

    def __init__(self, fn: Callable[[FastBrainRequest], FastBrainResult], *, name: str = "callable") -> None:
        self.fn = fn
        self.name = str(name)

    def classify(self, request: FastBrainRequest) -> FastBrainResult:
        result = self.fn(request)
        if not isinstance(result, FastBrainResult):
            raise TypeError("FastBrain callback must return FastBrainResult")
        return result


class ProviderFastBrain:
    """Tiny-label classifier backed by an existing Mary LLM provider.

    This is intentionally narrow: it asks an already configured provider for a
    single label from a fixed vocabulary. It does not receive Mary's identity
    prompt, cannot write state, and cannot execute tools. The caller retains
    deterministic floor/authority gates around the result.
    """

    def __init__(self, provider: Any, *, provider_name: str = "local") -> None:
        self.provider = provider
        self.provider_name = str(provider_name or "local")

    def classify(self, request: FastBrainRequest) -> FastBrainResult:
        from mary.llm.interface import LLMMessage

        labels = tuple(str(item).strip().casefold() for item in request.labels if str(item).strip())
        if not labels:
            if str(request.task).casefold() in {"stream_attention", "attention"}:
                labels = ("ignore", "notice", "respond")
            elif str(request.task).casefold() in {"directed_to", "target"}:
                labels = ("general", "mary")
            else:
                labels = ("unknown",)
        allowed = ", ".join(labels)
        context = dict(request.context or {})
        # Keep specialist prompts tiny. Values are bounded and treated as
        # non-authoritative context only.
        context_text = "; ".join(
            f"{str(k)[:40]}={str(v)[:100]}"
            for k, v in list(context.items())[:8]
        )
        prompt = (
            f"Task: {str(request.task)[:80]}. "
            f"Choose exactly one label from: {allowed}. "
            f"Context: {context_text or 'none'}. "
            f"Text: {str(request.text)[:500]}\n"
            "Return only the label."
        )
        response = self.provider.generate(
            [
                LLMMessage("system", "You are a tiny classification component. Return only one allowed label."),
                LLMMessage("user", prompt),
            ],
            temperature=0.0,
            max_tokens=12,
        )
        raw = " ".join(str(response.content or "").strip().casefold().split())
        label = next((item for item in labels if raw == item or raw.startswith(item + " ")), None)
        if label is None:
            # Conservatively search exact token only; never let free-form model
            # prose invent a new behavior label.
            words = {word.strip(".,:;!?`'\"") for word in raw.split()}
            label = next((item for item in labels if item in words), labels[0])
            confidence = .42
        else:
            confidence = .76
        result = FastBrainResult(
            label=label,
            confidence=confidence,
            scores={label: confidence},
            provider=str(getattr(response, "provider", self.provider_name) or self.provider_name),
            model=str(getattr(response, "model", "unknown") or "unknown"),
            metadata={"task": str(request.task)[:80], "authority": "ranking_only"},
        )
        record_turn_stage(
            "fast_brain", status="success", elapsed_ms=0.0,
            provider=result.provider, outcome=str(result.label)[:64],
        )
        return result


class RouterFastBrain:
    """Late-bind a tiny classifier to Mary's current local provider route.

    Remote capability nodes can connect after the canonical Core has already
    started. Resolving the provider on every small classification lets a Mac/PC
    llama.cpp node become useful without restarting Mary, while preserving the
    deterministic baseline whenever that replaceable device is unavailable.
    """

    def __init__(self, mary: Any, *, provider_name: str) -> None:
        self.mary = mary
        self.provider_name = str(provider_name or "local").strip().casefold()
        self.fallback = DeterministicFastBrain()

    def classify(self, request: FastBrainRequest) -> FastBrainResult:
        try:
            router = getattr(self.mary, "llm", None)
            provider = router.get_provider(self.provider_name) if router is not None else None
            if provider is None or not provider.is_available():
                return self.fallback.classify(request)
            return ProviderFastBrain(
                provider,
                provider_name=self.provider_name,
            ).classify(request)
        except Exception:
            return self.fallback.classify(request)


def fast_brain_from_environment(mary: Any) -> FastBrainProvider:
    """Resolve an optional local specialist without making it launch-critical.

    Provider-backed FastBrain routes are intentionally late-bound so a durable
    capability node may connect or reconnect after Mary Core starts.
    """
    import os

    name = os.getenv("MARY_FAST_BRAIN_PROVIDER", "deterministic").strip().casefold()
    if name not in {"llama_cpp", "ollama"}:
        return DeterministicFastBrain()
    return RouterFastBrain(mary, provider_name=name)
