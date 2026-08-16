"""
MaryV2 Runner

Simple terminal interface for interacting with Mary.

Run with:

    python -m scripts.run_mary
"""

from __future__ import annotations

from mary.core.mary import Mary


def main() -> None:
    """
    Start MaryV2 and provide a simple terminal interaction loop.
    """

    print("=" * 60)
    print("MaryV2")
    print("=" * 60)

    try:
        mary = Mary()

    except Exception as exc:
        print()
        print("Mary failed to initialize.")
        print(f"{type(exc).__name__}: {exc}")
        return

    # ------------------------------------------------------------
    # DURABLE MEMORY
    # ------------------------------------------------------------

    mary.config.ensure_directories()

    mary.memory.configure_persistence(
        mary.config.paths.memory / "memory.json",
        auto_save=True,
        load=True,
    )

    print()
    print("Mary initialized successfully.")

    # ------------------------------------------------------------
    # SYSTEM INFORMATION
    # ------------------------------------------------------------

    try:
        status = mary.status()

        print(f"Name: {status.get('name', 'Mary')}")

        cognition = status.get("cognition", {})

        print(
            "LLM Provider: "
            f"{cognition.get('llm', 'unknown')}"
        )

        print(
            "LLM Model: "
            f"{cognition.get('model', 'unknown')}"
        )

    except Exception as exc:
        print(
            "Warning: Could not read full system status: "
            f"{type(exc).__name__}: {exc}"
        )

    print()
    print("Mary is ready.")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)
    print()

    # ------------------------------------------------------------
    # INTERACTION LOOP
    # ------------------------------------------------------------

    while True:

        try:
            user_input = input("You: ").strip()

        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input.lower() in {
            "exit",
            "quit",
        }:
            break

        try:
            result = mary.process(
                user_input
            )

            response = getattr(
                result,
                "final_response",
                None,
            )

            if response is None:
                print(
                    "Mary: "
                    "[No response was generated.]"
                )
            else:
                print(
                    f"Mary: {response}"
                )

        except KeyboardInterrupt:
            print()
            break

        except Exception as exc:
            print()
            print(
                "[MaryV2 Error] "
                f"{type(exc).__name__}: {exc}"
            )
            print()

    mary.memory.save()

    print()
    print("Mary stopped.")


if __name__ == "__main__":
    main()