"""Deterministic/offline verifier for MaryV2 13.1 realtime cognitive infrastructure."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from mary.runtime.release import APP_VERSION, DESKTOP_PHASE
from mary.runtime.application import create_application
from mary.mobile.server import MOBILE_PROTOCOL_VERSION

ROOT = Path(__file__).resolve().parents[1]


def check(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(name)
    print(f"PASS  {name}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 13.1 REALTIME COGNITIVE INFRASTRUCTURE")
    print("=" * 72)
    check("release version is 13.1.1", APP_VERSION == "13.1.1")
    check("desktop phase is realtime cognitive infrastructure", DESKTOP_PHASE == "realtime-cognitive-infrastructure")
    check("mobile protocol generation 4", MOBILE_PROTOCOL_VERSION == "4")

    required = [
        "mary/realtime/attention.py",
        "mary/realtime/interaction.py",
        "mary/distributed/capabilities.py",
        "mary/distributed/nodes.py",
        "mary/mind/vector_index.py",
        "mary/mind/hybrid_retrieval.py",
        "mary/perception/director.py",
        "mary/training/feedback.py",
        "scripts/rebuild_semantic_vectors.py",
    ]
    for rel in required:
        check(f"{rel} exists", (ROOT / rel).is_file())

    previous = os.environ.get("MARY_RESERVOIR_STORAGE")
    os.environ["MARY_RESERVOIR_STORAGE"] = "ephemeral"
    try:
        with tempfile.TemporaryDirectory(prefix="mary131_verify_") as tmp:
            base = Path(tmp)
            app = create_application(
                memory_path=base / "memory" / "memory.json",
                developed_self_path=base / "personality" / "developed_self.json",
                preference_promotion_path=base / "personality" / "preference_promotion.json",
                auto_save=False,
                load_memory=False,
                load_developed_self=False,
                load_preference_promotion=False,
                name="verify_13_1",
            )
            mary = app.mary
            check("realtime interaction connected", mary.realtime.status().get("version") == "13.1")
            check("attention bus connected", mary.realtime.status().get("attention", {}).get("version") == "13.1")
            check("local compute node registered", mary.node_registry.snapshot().get("registered", 0) >= 1)
            check("hybrid retrieval connected", mary.mind.retrieval.status().get("version") == "13.1")
            check("vector index is derived authority", mary.mind.retrieval.status().get("vector_index", {}).get("authority") == "derived retrieval cache only")
            check("perception boundary connected", mary.perception_director.snapshot().get("version") == "13.1")
            check("explicit feedback dataset connected", mary.training_feedback.status().get("version") == "13.1")
            authority = mary.system_contract.snapshot(mary).get("authority", {})
            for key in ("realtime_attention", "perception_boundary", "distributed_compute", "semantic_retrieval", "response_feedback"):
                check(f"system contract declares {key}", key in authority)
            app.close()
    finally:
        if previous is None:
            os.environ.pop("MARY_RESERVOIR_STORAGE", None)
        else:
            os.environ["MARY_RESERVOIR_STORAGE"] = previous

    mobile = (ROOT / "mobile_web" / "app.js").read_text(encoding="utf-8")
    native = (ROOT / "mobile_native" / "MaryMobile" / "www" / "app.js").read_text(encoding="utf-8")
    desktop = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    worker = (ROOT / "mobile_web" / "sw.js").read_text(encoding="utf-8")
    check("mobile realtime workspace present", all(label in mobile for label in ("REALTIME INTERACTION", "ATTENTION BUS", "HYBRID MEMORY RETRIEVAL", "COMPUTE NODES", "MARY EVALUATION SET")))
    check("mobile explicit response feedback present", "recordResponseFeedback" in mobile and "data-response-feedback" in mobile)
    check("native mobile bundle synchronized", mobile == native)
    check("mobile cache generation 13.1", "maryv2-mobile-shell-v13-1" in worker)
    check("desktop realtime diagnostics present", all(label in desktop for label in ("REALTIME COGNITIVE INFRASTRUCTURE", "Attention Bus", "Hybrid Memory Retrieval", "Compute Nodes")))

    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    check("vector retrieval defaults are opt-in/lazy", "MARY_VECTOR_RETRIEVAL=auto" in env and "MARY_VECTOR_INDEX_LIMIT=1000" in env)
    check("release does not package private .env", not (ROOT / ".env").exists())

    print("=" * 72)
    print("MARYV2 13.1 REALTIME COGNITIVE INFRASTRUCTURE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
