from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_core_owns_self_inspection_and_surface_authority() -> None:
    root = _text("MARY_ROOT.md")
    mary = _text("mary/core/mary.py")
    cognition = _text("mary/cognition/orchestrator.py")
    nodes = _text("mary/distributed/nodes.py")

    assert "Self/runtime inspection is Core-owned evidence" in root
    assert '"self_query_type": "runtime_inspection"' in mary
    assert "def _runtime_self_inspection_response" in mary
    assert '"self_understanding"' in mary
    assert '"capabilities"' in mary
    assert 'return self_intent("runtime_inspection")' in cognition
    assert "Core owns Mary state" in nodes


def test_current_information_and_probe_memory_rules_are_shared_core_behavior() -> None:
    cognition = _text("mary/cognition/orchestrator.py")
    dashboard = _text("mary/desktop/dashboard.py")

    assert "come out|coming out|release|launch" in cognition
    assert "is_creator_record_conversation_safe(item)" in dashboard


def test_pwa_and_legacy_wrapper_share_current_surface_contract() -> None:
    web = ROOT / "mobile_web"
    compat = ROOT / "mobile_native" / "MaryMobile" / "www"

    for name in ("app.js", "sw.js", "polish-13-7.css"):
        assert (web / name).read_bytes() == (compat / name).read_bytes()

    app = (web / "app.js").read_text(encoding="utf-8")
    assert "'Core connected'" in app
    assert "Core ${core.architecture||'13.3'} reachable" not in app
    assert "Vector index" in app
    assert "Not built" in app
    assert "tts.server_available" in app
    assert "Switch Voice Route to Auto or Device voice." in app


def test_desktop_and_cli_use_same_degraded_state_vocabulary() -> None:
    desktop = _text("desktop/src/main.js")
    desktop_voice = _text("mary/desktop/voice.py")
    cli = _text("mary/runtime/application.py")

    assert "Vector index" in desktop
    assert "Not built" in desktop
    assert "No external compute connected. Mary continues on the Core provider route." in desktop
    assert "Server voice · text remains available if voice degrades" in desktop
    assert 'tts.get("server_available", tts.get("enabled", False))' in desktop_voice
    assert "self._core_enabled = False" in desktop_voice
    assert '"desktop_local_fallback"' in desktop_voice

    assert "Vector index: not built (structured/lexical recall remains active)" in cli
    assert "No external compute connected. Mary continues on the Core/provider route." in cli


def test_voice_provider_and_mobile_status_never_expose_raw_vendor_body() -> None:
    provider = _text("mary/voice/providers/elevenlabs.py")
    mobile = _text("mary/mobile/audio.py")

    assert "_safe_http_failure_message" in provider
    assert 'message += f" {detail}"' not in provider
    assert "provider account requires payment" in provider

    assert '"configured": tts_enabled' in mobile
    assert '"server_available": tts_available' in mobile
    assert '"degraded": bool(tts_enabled and not tts_available)' in mobile
    assert '"fallback": "device"' in mobile


def test_native_iphone_prefers_core_but_falls_back_to_device_voice_safely() -> None:
    client = _text("ios/MaryV2iOS/Sources/MaryCoreClient.swift")
    state = _text("ios/MaryV2iOS/Sources/AppState.swift")
    playback = _text("ios/MaryV2iOS/Sources/VoicePlayback.swift")
    call = _text("ios/MaryV2iOS/Sources/VoiceCallView.swift")

    assert "safeHTTPErrorMessage" in client
    assert "Mary Core request failed (HTTP" in client
    assert "AVSpeechSynthesizer" in playback
    assert "func speakDevice" in playback
    assert "tts[\"server_available\"] ?? tts[\"enabled\"]" in state
    assert 'voiceProvider = "iPhone voice"' in state
    assert "Core voice unavailable · iPhone voice fallback ready" in call


def test_diagnostics_distinguish_configured_from_live_readiness() -> None:
    audit = _text("mary/runtime/wiring_audit.py")
    doctor = _text("scripts/check_mary_13.py")

    assert '"tts_configured"' in audit
    assert '"tts_ready"' in audit
    assert '"tts_degraded"' in audit
    assert 'tts.get("server_available", tts.get("enabled", False))' in audit

    assert "connected /" in doctor
    assert "vector index=" in doctor
    assert "not built (structured/lexical recall active)" in doctor
    assert '"DEGRADED" if tts_configured else "OFF"' in doctor


def test_bounded_engineering_loop_is_shared_and_has_no_generic_shell() -> None:
    engineering = _text("mary/distributed/engineering.py")
    tasks = _text("mary/distributed/tasks.py")
    permissions = _text("mary/distributed/permissions.py")
    node = _text("mary/desktop/device_node.py")
    cognition = _text("mary/cognition/orchestrator.py")
    mary = _text("mary/core/mary.py")
    service = _text("mary/core/service.py")

    assert '"engineering.repair.plan"' in engineering
    assert '"engineering.repo.apply"' in engineering
    assert '"engineering.tests.targeted"' in engineering
    assert "shell=False" in engineering
    assert "TemporaryDirectory" in engineering
    assert "expected_sha256" in engineering
    assert "proposal_id" in engineering
    assert "engineering.shell" not in engineering

    assert "*ENGINEERING_CAPABILITIES" in tasks
    assert "*ENGINEERING_CAPABILITIES" in permissions
    assert "engineering_capability_descriptors" in node
    assert "_execute_engineering" in node

    assert 'return self_intent("engineering_repair")' in cognition
    assert 'return self_intent("engineering_apply")' in cognition
    assert "self.engineering_dispatcher" in mary
    assert "def _engineering_action" in service
    assert "This does not commit, push, merge, or deploy" in service


def test_home_nodes_remain_replaceable_workers_not_shadow_mary_instances() -> None:
    home = _text("scripts/run_home_node.py")
    windows = _text("scripts/run_windows_node.py")

    assert "gateway_from_environment" in home
    assert "DesktopCapabilityNodeAgent" in home
    assert "DeviceExecutionPermissions" in home
    assert "create_application(" not in home
    assert "MaryApplication(" not in home
    assert "Mary(" not in home

    assert "run_home_node_main" in windows
    assert "second windows_node" in windows


def test_docs_describe_one_mary_across_current_surfaces() -> None:
    registry = _text("docs/architecture/SYSTEM_REGISTRY.md")
    legacy_mobile = _text("mobile_native/README.md")

    assert "CURRENT CORE CONTRACT" in registry
    assert "Core voice preferred with iPhone system-speech fallback" in registry
    assert "ACTIVE DEGRADED-SAFE" in registry
    assert "never Mary identity, relationship state or canonical memory" in legacy_mobile
