from __future__ import annotations

import argparse
import json

from mary.cognition.runtime_coordination import CharacterRuntimeCoordinator
from mary.core.mary import Mary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", default=[])
    args = parser.parse_args()
    text = " ".join(args.text).strip() or "Mary, what do you think about where we are with the project?"

    mary = Mary()
    intent = mary.cognition.detect_intent(text)
    state = mary.turn_mind.build(input_text=text, intent=intent, recent_conversation=[])
    plan = CharacterRuntimeCoordinator().plan_from_turn_state(state)
    print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
