"""Display-safe check of Mary character authority wiring."""
from __future__ import annotations
import json
from mary.core.mary import Mary


def main() -> int:
    mary = Mary()
    payload = {
        "sourcebook": mary.character_sourcebook.snapshot(),
        "evaluation": mary.character_evaluation.snapshot(),
        "root_authority": mary.root_authority.snapshot(mary),
        "contract_issues": mary.system_contract.validate(mary),
        "turnmind_shares_sourcebook": mary.turn_mind.character_sourcebook is mary.character_sourcebook,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not payload["contract_issues"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
