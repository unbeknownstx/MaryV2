from __future__ import annotations

from mary.runtime.introspection import RuntimeIntrospection, is_personal_runtime_reaction


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def main() -> None:
    print("=" * 72)
    print("MARY V2 BREAKTHROUGH 12.3 - MIXED RUNTIME + PERSONAL INTENT")
    print("=" * 72)
    check("runtime introspection version is Breakthrough 12.3", RuntimeIntrospection.VERSION == "v2-breakthrough-12.3")
    check("MacBook first-time reaction stays personal", is_personal_runtime_reaction("we're running on my MacBook for the first time what do you think"))
    check("Replit phone reaction stays personal", is_personal_runtime_reaction("idk im working on u from replit on my phone right now what do u think"))
    check("pure model availability remains runtime introspection", not is_personal_runtime_reaction("what models can you use right now"))
    check("pure host location remains runtime introspection", not is_personal_runtime_reaction("where are you running right now"))
    check("pure portability question remains deterministic", not is_personal_runtime_reaction("does anything about how you work change because were not on my pc"))
    print("=" * 72)
    print("BREAKTHROUGH 12.3 VERIFIED")


if __name__ == "__main__":
    main()
