from __future__ import annotations

from types import SimpleNamespace

from scripts import run_release_verification as release


def test_release_registry_covers_every_current_verifier_script():
    registered = tuple(module for _, module in release.OFFLINE_VERIFIERS)
    discovered = release.discover_verifier_modules()

    assert len(registered) == len(set(registered))
    assert set(registered) == set(discovered)


def test_offline_environment_forcibly_disables_live_llm(monkeypatch):
    monkeypatch.setenv("MARY_RUN_LIVE_TESTS", "1")

    environment = release._offline_environment()

    assert "MARY_RUN_LIVE_TESTS" not in environment


def test_normal_pytest_run_uses_offline_environment(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("MARY_RUN_LIVE_TESTS", "1")
    monkeypatch.setattr(release.subprocess, "run", fake_run)

    assert release.run_pytest() is True
    assert captured["command"][-2:] == ["tests", "-q"]
    assert "MARY_RUN_LIVE_TESTS" not in captured["env"]


def test_live_llm_is_explicit_and_scoped_to_dedicated_test(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(release.subprocess, "run", fake_run)

    assert release.run_live_llm() is True
    assert release.LIVE_LLM_TEST in captured["command"]
    assert captured["env"]["MARY_RUN_LIVE_TESTS"] == "1"
    assert captured["command"][:3] == [release.sys.executable, "-m", "pytest"]


def test_verifier_runner_does_not_leak_release_cli_arguments(monkeypatch):
    seen = {}

    def verifier_main():
        seen["argv"] = release.sys.argv[:]
        return 0

    fake_module = SimpleNamespace(main=verifier_main)
    monkeypatch.setattr(
        release.importlib,
        "import_module",
        lambda module: fake_module,
    )
    monkeypatch.setattr(
        release.sys,
        "argv",
        ["run_release_verification.py", "--offline"],
    )

    assert release.run_verifier("fake", "scripts.verify_fake") is True
    assert seen["argv"] == ["scripts.verify_fake"]
    assert release.sys.argv == ["run_release_verification.py", "--offline"]
