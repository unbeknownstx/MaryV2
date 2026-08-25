"""Deterministically verify the MaryV2 13.0 evolution layer.

No network calls are made.  The verifier checks the new intentional-conversation,
growth, Voice Lab, mobile protocol, and frontend/native synchronization contracts
without touching the user's normal persistent state.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from mary.conversation.engagement import ConversationEngagement
from mary.mobile.server import MOBILE_PROTOCOL_VERSION
from mary.mobile.voice_lab import BASELINE
from mary.runtime.application import create_application
from mary.runtime.release import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def _check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 13.0 CONNECTED DEVELOPMENT EVOLUTION")
    print("=" * 72)

    _check("13.0 foundation remains installed in current release", APP_VERSION in {"13.0.0", "13.1.1"})
    _check("mobile protocol preserves 13.0+ generation", MOBILE_PROTOCOL_VERSION in {"3", "4"})
    _check(
        "natural ElevenLabs baseline is neutral",
        BASELINE == {
            "stability": 0.50,
            "similarity": 0.75,
            "style": 0.0,
            "speed": 1.0,
            "speaker_boost": False,
        },
    )

    with tempfile.TemporaryDirectory(prefix="maryv2_13_verify_") as directory:
        root = Path(directory)

        engagement = ConversationEngagement()
        engagement.configure(root / "engagement.json")
        plan = engagement.begin_turn("let's talk for a while and get to know me")
        _check("intentional conversation cue opens engaged mode", plan.effective_mode == "engaged")
        engagement.complete_turn("What matters to you most when you're creating something?")
        reloaded = ConversationEngagement()
        reloaded.configure(root / "engagement.json")
        _check(
            "intentional conversation thread survives restart",
            reloaded.status()["active_session"]["mode"] == "engaged"
            and reloaded.status()["active_session"]["turns_remaining"] == 7,
        )

        app = create_application(
            memory_path=root / "memory" / "memory.json",
            developed_self_path=root / "personality" / "developed.json",
            preference_promotion_path=root / "personality" / "promotion.json",
        )
        mary = app.mary
        before = mary.growth.status()["journal"]["records"]
        result = mary.process("go ahead and ask me some questions and get to know me")
        after = mary.growth.status()["journal"]["records"]
        _check("learning invitation uses a real conversational question", "?" in result.final_response)
        _check("completed meaningful turn enters the experience journal", after == before + 1)
        _check(
            "model dialogue is not durable self-development evidence",
            mary.growth.status()["policy"]["model_dialogue_counts_as_self_evidence"] is False,
        )
        app.close()

    mobile = (ROOT / "mobile_web" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "mobile_web" / "index.html").read_text(encoding="utf-8")
    native = (ROOT / "mobile_native" / "MaryMobile" / "www" / "app.js").read_text(encoding="utf-8")
    _check("mobile exposes Talk and Deep controls", 'data-conversation-mode="engaged"' in html and 'data-conversation-mode="deep"' in html)
    _check("mobile exposes Growth workspace", 'data-open="growth"' in html and "renderGrowth" in mobile)
    _check("mobile separates dislikes from preferences", "DISLIKES / AVERSIONS" in mobile)
    _check("mobile exposes private Voice Lab controls", "saveVoiceProfile" in mobile and "resetVoiceBaseline" in mobile)
    _check("native iPhone web bundle matches mobile app source", native == mobile)

    print("=" * 72)
    print("MARYV2 13.0 EVOLUTION VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
