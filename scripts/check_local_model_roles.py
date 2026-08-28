"""Show the Windows node's bounded Ollama role-to-model mapping."""
from __future__ import annotations

from mary.desktop.device_node import _ollama_model_for_role
from mary.llm.providers.ollama import OllamaProvider


def main() -> int:
    print("MARYV2 LOCAL MODEL ROLES")
    print("=" * 64)
    for role in ("fast", "conversation", "general", "utility"):
        print(f"{role:14} {_ollama_model_for_role(role)}")
    provider = OllamaProvider()
    print(f"Ollama available: {'YES' if provider.is_available() else 'NO'}")
    print("Core requests roles only; the device owns concrete model selection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
