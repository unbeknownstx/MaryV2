"""Deterministic MaryV2 13.68 Desktop convergence gate.

This is a source-level/offline gate for the contracts that must remain connected
across Desktop presentation, canonical Core projection, local inference, memory,
performance context, and personal avatar assets. It intentionally performs no
provider/network calls and reads no private memory contents.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def check(condition: bool, label: str, failures: list[str]) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    failures: list[str] = []

    vite = text("desktop/vite.config.js")
    shell = text("desktop/public/product-shell-13-68.css")
    main_js = text("desktop/src/main.js")
    dashboard = text("mary/desktop/dashboard.py")
    bridge = text("mary/desktop/bridge.py")
    supervisor = text("mary/desktop/runtime_supervisor.py")
    local_runtime = text("mary/llm/providers/local_runtime.py")
    router = text("mary/llm/router.py")
    natural = text("mary/relationship/natural_learning.py")
    frontend_build = text("mary/desktop/frontend_build.py")
    recovery = text("mary/desktop/continuity_recovery.py")

    check("product-shell-13-68.css" in vite, "13.68 final presentation layer is injected", failures)
    check("emptyOutDir: false" in vite, "Vite preserves personal gitignored avatar output", failures)
    check("_preserve_local_avatar_assets" in frontend_build and "MARY_DESKTOP_VRM_PATH" in frontend_build,
          "personal VRM survives rebuild and has explicit recovery path", failures)

    check('.app-shell:not([data-screen="chat"]) .composer-deck' in shell,
          "non-Talk workspaces hide the conversation composer", failures)
    check("background: #090d1c !important" in shell and "backdrop-filter: none !important" in shell,
          "workspace surface is opaque and unblurred", failures)

    check("data-performance-context" in main_js and "setPerformanceContext" in bridge,
          "private/casual/focus/streamer/performance modes are actionable", failures)
    check("aria-pressed" in main_js and "chip active" not in main_js,
          "performance modes expose selected-state semantics", failures)

    check("memory_archive" in dashboard and "shared_history" in dashboard and "milestones" in dashboard,
          "Memory screen projects canonical memory plus relationship continuity", failures)
    check("def _memory_highlights" in dashboard and "_memory_archive(mary)" in dashboard,
          "memory highlights fall back to real canonical archive records", failures)
    check("discover_local_continuity" in recovery and "read_only" in recovery,
          "older local continuity can be audited without automatic mutation", failures)

    check('_env_bool("MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE", True)' in supervisor,
          "creator Desktop auto-authorizes ready local conversation compute", failures)
    check('permissions.allow("llm.local")' in supervisor,
          "auto-authorization is scoped to llm.local", failures)
    check('permissions.allow("filesystem")' not in supervisor and 'permissions.allow("desktop_apps")' not in supervisor,
          "local conversation permission does not widen tool authority", failures)
    check("lm_studio" in local_runtime and "ollama" in local_runtime and "llama_cpp" in local_runtime,
          "replaceable LM Studio/Ollama/llama.cpp runtime fabric remains available", failures)
    check("local_device" in router and "conversation_provider_order" in router,
          "router retains the local-device conversation lane", failures)

    check('return "fact"' in natural and 'r"^my [a-z0-9 _-]{1,80} is .+"' in natural,
          "ordinary direct creator facts can enter durable relationship learning", failures)

    check("Fast chat model</span><strong>Groq · llama-3.1-8b-instant" in vite
          and "Conversation route</span><strong>Automatic · see live Runtime route" in vite,
          "generated Desktop retires stale fixed-Groq product copy", failures)

    print("-" * 72)
    if failures:
        print(f"13.68 Desktop convergence: FAIL ({len(failures)} contract(s))")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("13.68 Desktop convergence: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
