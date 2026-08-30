"""Deterministic verifier for MaryV2 12.12.3 Production Hybrid Dialogue."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ISOLATION_PREFIX = "maryv2-production-verifier-"
_STRIP_ENV = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "MARY_LLM_PROVIDER",
    "MARY_LLM_MODEL",
    "MARY_LLM_FALLBACKS",
    "MARY_LLM_ROUTING_STRATEGY",
    "MARY_LLM_FREE_ORDER",
    "MARY_LLM_CONVERSATION_ORDER",
    "MARY_LLM_EXPERT_PROVIDER",
)
_OVERRIDE_ENV = {
    "MARY_RESERVOIR_STORAGE": "memory",
    "MARY_LOCAL_MIND_ENABLED": "true",
    "MARY_LOCAL_DIALOGUE_ENABLED": "true",
    "MARY_QWEN_SHADOW_ENABLED": "0",
    "MARY_LOCAL_MIND_SHADOW_ENABLED": "0",
    "MARY_HYBRID_QWEN_SHADOW_ENABLED": "0",
}


def _validate_isolation_root(path: str | Path) -> Path:
    candidate = Path(path)
    system_temp = Path(tempfile.gettempdir()).resolve()
    if candidate.is_symlink():
        raise RuntimeError("refusing verifier cleanup of a symlink")
    is_junction = getattr(candidate, "is_junction", None)
    if callable(is_junction) and is_junction():
        raise RuntimeError("refusing verifier cleanup of a junction")
    resolved = candidate.resolve()
    if resolved.parent != system_temp or not resolved.name.startswith(ISOLATION_PREFIX):
        raise RuntimeError("verifier isolation root is outside bounded system temp")
    return resolved


@contextmanager
def isolated_verifier_environment():
    """Install fresh state before any Mary/config import and restore exactly."""

    tracked = tuple(dict.fromkeys((
        *_STRIP_ENV,
        *_OVERRIDE_ENV,
        "MARY_DATA_DIR",
        "MARY_ENV_FILE",
    )))
    previous = {name: os.environ.get(name) for name in tracked}
    root = Path(tempfile.mkdtemp(prefix=ISOLATION_PREFIX)).resolve()
    _validate_isolation_root(root)
    data_dir = root / "state"
    env_file = root / "no-live-config"
    data_dir.mkdir(parents=True, exist_ok=False)
    if env_file.exists():
        raise RuntimeError("verifier requires a nonexistent MARY_ENV_FILE target")
    try:
        for name in _STRIP_ENV:
            os.environ.pop(name, None)
        os.environ.update(_OVERRIDE_ENV)
        os.environ["MARY_DATA_DIR"] = str(data_dir)
        os.environ["MARY_ENV_FILE"] = str(env_file)
        yield {"root": root, "data": data_dir, "env_file": env_file}
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if root.exists():
            shutil.rmtree(_validate_isolation_root(root))


def check(condition: bool, message: str) -> bool:
    print(f"[{'OK' if condition else 'FAIL'}] {message}")
    return bool(condition)


def _run_isolated_checks() -> int:
    # These imports are intentionally inside the already-active isolation
    # context.  Importing this verifier alone must never trigger dotenv or
    # persistent-state discovery.
    from mary.core.config import Config
    from mary.core.mary import Mary
    from mary.llm.router import LLMRouter
    from mary.runtime.release import APP_VERSION

    print("=" * 76)
    print("MARYV2 12.12.3 PRODUCTION HYBRID DIALOGUE")
    print("=" * 76)
    checks: list[bool] = []
    checks.append(check(
        APP_VERSION in {"12.12.3", "13.0.0", "13.1.1"},
        "12.12.3 production-hybrid foundation remains installed",
    ))

    for relative in (
        "mary/mind/local_response_projector.py",
        "mary/mind/local_response_audit.py",
        "scripts/benchmark_production_hybrid_dialogue.py",
        "scripts/benchmark_production_hybrid_dialogue_windows.ps1",
        "docs/history/root-archive/release-notes/START_HERE_12_12_3.md",
        "docs/history/root-archive/release-notes/TEST_RESULTS_12_12_3.md",
        "tests/mind/test_production_local_mind_v2.py",
        "tests/core/test_production_hybrid_core_12_12_3.py",
        "tests/desktop/test_production_hybrid_trace_12_12_3.py",
    ):
        checks.append(check((ROOT / relative).is_file(), f"surface exists: {relative}"))

    default_config = Config()
    expected_data_root = Path(os.environ["MARY_DATA_DIR"]).resolve()
    if default_config.paths.data.resolve() != expected_data_root:
        raise RuntimeError("verifier Config resolved a non-isolated data root")
    default_router = LLMRouter(default_config)
    checks.append(check(
        default_config.llm.routing_strategy == "free_first"
        and default_router._provider_order(None)
        == ["groq", "gemini", "openrouter", "ollama"],
        "free-first provider ordering is unchanged",
    ))
    checks.append(check(
        default_router._provider_order(None, route="private") == ["ollama"],
        "private/offline routing remains Ollama-only",
    ))
    checks.append(check(
        default_router._provider_order(None, route="expert") == ["openai"],
        "paid OpenAI remains the explicit expert route",
    ))

    production_sources = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "mary/core/mary.py",
            "mary/mind/character_mind.py",
            "mary/mind/local_response_projector.py",
            "mary/mind/local_response_audit.py",
        )
    ).casefold()
    checks.append(check(
        "qwen3:1.7b" not in production_sources,
        "qwen3:1.7b is not a production response engine",
    ))

    mary = Mary()
    try:
        provider_calls = 0

        def forbidden_provider(*_args, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            raise AssertionError("eligible local response reached a provider")

        mary.llm.generate = forbidden_provider  # type: ignore[method-assign]
        result = mary.process("hey mary")
        reasoning = dict(result.reasoning.metadata or {})
        checks.append(check(
            result.metadata.get("handled_by") == "mary_local_mind"
            and reasoning.get("provider") == "local/mind"
            and reasoning.get("response_engine") == "local_composer_v2"
            and reasoning.get("response_class") == "social_low_risk",
            "eligible production social turn uses LocalComposerV2",
        ))
        checks.append(check(
            provider_calls == 0
            and reasoning.get("provider_attempts") == []
            and reasoning.get("provider_attempt_timings") == [],
            "accepted local production turn makes zero provider calls",
        ))
        local = mary.mind.try_respond(
            "hey mary",
            intent=mary.cognition.detect_intent("hey mary"),
            context={"mind_state": {"continuity": {"allow_follow_up_question": False}}},
        )
        canonical = dict(local.metadata.get("canonical_plan") or {})
        checks.append(check(
            canonical.get("authoritative_state_owner") is None
            and canonical.get("persistence") == "none",
            "typed response plan is a nonpersistent authority projection",
        ))
        checks.append(check(
            local.metadata.get("shadow_enabled") is False
            and local.metadata.get("shadow_model") is None,
            "production Qwen shadow remains disabled",
        ))
    finally:
        mary.mind.close()

    ok = all(checks)
    print("=" * 76)
    print(
        "MARYV2 12.12.3 PRODUCTION HYBRID DIALOGUE VERIFIED"
        if ok
        else "MARYV2 12.12.3 PRODUCTION HYBRID DIALOGUE VERIFICATION FAILED"
    )
    return 0 if ok else 1


def main() -> int:
    with isolated_verifier_environment() as isolation:
        if Path(os.environ["MARY_DATA_DIR"]).resolve() != isolation["data"].resolve():
            raise RuntimeError("verifier did not resolve its fresh isolated data root")
        if Path(os.environ["MARY_ENV_FILE"]).exists():
            raise RuntimeError("verifier MARY_ENV_FILE target must remain nonexistent")
        return _run_isolated_checks()


if __name__ == "__main__":
    raise SystemExit(main())
