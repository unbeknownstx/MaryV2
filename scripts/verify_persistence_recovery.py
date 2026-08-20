"""Verify bounded atomic MaryV2 persistence and backup recovery."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mary.governance.limits import RuntimeLimits
from mary.memory.manager import MemoryManager


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 PERSISTENCE RECOVERY")
    print("=" * 72)
    limits = RuntimeLimits(episodic_capacity=8, semantic_capacity=8, backup_generations=2)
    with tempfile.TemporaryDirectory(prefix="maryv2_recovery_") as tmp:
        path = Path(tmp) / "memory.json"
        memory = MemoryManager(storage_path=path, auto_save=True, limits=limits)
        memory.remember("first recovery marker", memory_type="episodic", importance=0.9)
        memory.remember("second recovery marker", memory_type="semantic", importance=0.9, metadata={"subject": "recovery", "predicate": "marker"})
        check("primary memory state is written", path.exists())
        check("finite backup generation exists after repeated writes", path.with_suffix(path.suffix + ".bak1").exists())
        path.write_text("{broken", encoding="utf-8")
        recovered = MemoryManager(storage_path=path, auto_save=False, limits=limits)
        recovered.load()
        status = recovered.status().get("persistence", {})
        check("corrupt primary recovers from finite backup", bool(status.get("recovered_from_backup")))
        check("backup chain is finite", len(list(Path(tmp).glob("memory.json.bak*"))) <= limits.backup_generations)
        # Ensure payload remains valid after explicit restoration.
        recovered.restore_recovered_primary()
        json.loads(path.read_text(encoding="utf-8"))
        check("recovered primary is valid JSON", True)
    print("=" * 72)
    print("PERSISTENCE RECOVERY VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
