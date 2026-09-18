from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from mary.distributed.engineering import (
    ENGINEERING_CAPABILITIES,
    EngineeringWorker,
    engineering_capability_descriptors,
    sanitize_engineering_task_args,
)
from mary.distributed.permissions import DeviceExecutionPermissions


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "mary").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "mary" / "sample.py").write_text(
        'def greeting():\n    return "hello"\n',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_sample.py").write_text(
        'def test_truth():\n    assert True\n',
        encoding="utf-8",
    )
    return tmp_path


def test_engineering_capabilities_are_deny_by_default_and_never_include_shell(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setenv("MARY_ENGINEERING_REPO_ROOT", str(root))

    class _Local:
        def __init__(self, role="general"):
            self.role = role

        def runtime_status(self):
            return {"available": True, "runtime": "ollama", "model": "qwen-coder"}

    monkeypatch.setattr("mary.distributed.engineering.LocalRuntimeProvider", _Local)

    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    descriptors = engineering_capability_descriptors(permissions)

    assert ENGINEERING_CAPABILITIES
    assert all(item.metadata["execution_authorized"] is False for item in descriptors)
    assert all("shell" not in item.name for item in descriptors)
    assert "engineering.repair.plan" in {item.name for item in descriptors}
    assert permissions.is_allowed("engineering.repo.apply") is False

    permissions.allow("engineering.repair.plan")
    refreshed = engineering_capability_descriptors(permissions)
    repair = next(item for item in refreshed if item.name == "engineering.repair.plan")
    assert repair.metadata["execution_authorized"] is True
    assert repair.available is True


def test_repair_capability_is_not_advertised_ready_without_local_model(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setenv("MARY_ENGINEERING_REPO_ROOT", str(root))

    class _Local:
        def __init__(self, role="general"):
            self.role = role

        def runtime_status(self):
            return {"available": False, "runtime": "ollama", "model": "qwen-coder"}

    monkeypatch.setattr("mary.distributed.engineering.LocalRuntimeProvider", _Local)

    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    permissions.allow("engineering.repair.plan")
    repair = next(
        item
        for item in engineering_capability_descriptors(permissions)
        if item.name == "engineering.repair.plan"
    )

    assert repair.available is False
    assert repair.readiness == "unavailable"


def test_exact_patch_proposal_does_not_modify_repository(tmp_path):
    root = _repo(tmp_path)
    worker = EngineeringWorker(root)
    source = (root / "mary" / "sample.py").read_text(encoding="utf-8")
    expected = sha256(source.encode("utf-8")).hexdigest()

    proposal = worker.propose([
        {
            "path": "mary/sample.py",
            "expected_sha256": expected,
            "edits": [{"old": 'return "hello"', "new": 'return "hi"'}],
        }
    ])

    assert proposal["ok"] is True
    assert '-    return "hello"' in proposal["diff"]
    assert '+    return "hi"' in proposal["diff"]
    assert (root / "mary" / "sample.py").read_text(encoding="utf-8") == source


def test_repository_apply_requires_exact_hash_and_never_commits_or_pushes(tmp_path):
    root = _repo(tmp_path)
    worker = EngineeringWorker(root)
    source = (root / "mary" / "sample.py").read_text(encoding="utf-8")
    expected = sha256(source.encode("utf-8")).hexdigest()

    result = worker.apply([
        {
            "path": "mary/sample.py",
            "expected_sha256": expected,
            "edits": [{"old": 'return "hello"', "new": 'return "hi"'}],
        }
    ])

    assert result["applied"] is True
    assert "No commit, push, or deploy" in result["summary"]
    assert 'return "hi"' in (root / "mary" / "sample.py").read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="stale engineering patch"):
        worker.apply([
            {
                "path": "mary/sample.py",
                "expected_sha256": expected,
                "edits": [{"old": 'return "hi"', "new": 'return "hey"'}],
            }
        ])


def test_repair_plan_uses_local_model_but_keeps_exact_proposal_node_local(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    worker = EngineeringWorker(root)
    source = (root / "mary" / "sample.py").read_text(encoding="utf-8")
    expected = sha256(source.encode("utf-8")).hexdigest()

    class _Response:
        content = (
            '{"summary":"Tighten greeting","changes":[{"path":"mary/sample.py",'
            f'"expected_sha256":"{expected}","edits":[{{"old":"return \\"hello\\"",'
            '"new":"return \\"hi\\""}]}]}'
        )
        model = "qwen-coder"

    class _Local:
        def __init__(self, role="general"):
            self.role = role

        def is_available(self):
            return True

        def runtime_name(self):
            return "ollama"

        def model_name(self):
            return "qwen-coder"

        def generate_constrained(self, request):
            return _Response()

    monkeypatch.setattr("mary.distributed.engineering.LocalRuntimeProvider", _Local)

    plan = worker.repair_plan("change the greeting from hello to hi", max_files=4)

    assert plan["proposal_id"].startswith("engineering_proposal_")
    assert "mary/sample.py" in plan["files"]
    assert (root / "mary" / "sample.py").read_text(encoding="utf-8") == source
    assert "proposal only" in " ".join(plan["warnings"]).lower()

    applied = worker.apply(proposal_id=plan["proposal_id"])
    assert applied["applied"] is True
    assert 'return "hi"' in (root / "mary" / "sample.py").read_text(encoding="utf-8")


def test_typed_test_runner_uses_disposable_sandbox_not_live_checkout(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    worker = EngineeringWorker(root)
    observed = {}

    def fake_run(argv, *, cwd, text, capture_output, timeout, check, shell, env):
        observed["argv"] = list(argv)
        observed["cwd"] = Path(cwd)
        observed["shell"] = shell
        assert Path(cwd) != root
        assert not (Path(cwd) / ".git").exists()
        assert (Path(cwd) / "tests" / "test_sample.py").exists()
        return SimpleNamespace(returncode=0, stdout="1 passed", stderr="")

    monkeypatch.setattr("mary.distributed.engineering.subprocess.run", fake_run)

    result = worker.run_targeted_tests(["tests/test_sample.py"])

    assert result["ok"] is True
    assert result["workspace_isolated"] is True
    assert observed["shell"] is False
    assert observed["argv"][:3] == [sys.executable, "-m", "pytest"]


def test_remote_repository_apply_requires_node_local_proposal_id():
    with pytest.raises(ValueError, match="proposal_id"):
        sanitize_engineering_task_args(
            "engineering.repo.apply",
            {
                "changes": [
                    {
                        "path": "mary/sample.py",
                        "expected_sha256": "0" * 64,
                        "edits": [{"old": "x", "new": "y"}],
                    }
                ]
            },
        )

    sanitized = sanitize_engineering_task_args(
        "engineering.repo.apply",
        {"proposal_id": "engineering_proposal_abc123"},
    )
    assert sanitized == {"proposal_id": "engineering_proposal_abc123"}


def test_engineering_args_reject_arbitrary_paths_and_commands():
    with pytest.raises(ValueError):
        sanitize_engineering_task_args(
            "engineering.tests.targeted",
            {"paths": ["../outside.py"]},
        )

    assert "engineering.shell" not in ENGINEERING_CAPABILITIES
