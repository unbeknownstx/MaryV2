"""Bounded software-engineering capability worker for MaryV2 nodes.

The worker is replaceable infrastructure. It never owns Mary identity/state and
never exposes a generic shell. Read/plan/test work is typed. Repository writes
are a separate capability and remain device-permission gated.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from uuid import uuid4

from mary.distributed.capabilities import CapabilityDescriptor
from mary.llm.interface import (
    GenerationCost,
    GenerationOperation,
    GenerationPrivacy,
    GenerationRequest,
    LLMMessage,
    generation_correlation_id,
)
from mary.llm.providers.local_runtime import LocalRuntimeProvider


ENGINEERING_CAPABILITIES = frozenset({
    "engineering.repo.inspect",
    "engineering.repair.plan",
    "engineering.patch.propose",
    "engineering.repo.apply",
    "engineering.tests.targeted",
    "engineering.tests.full",
    "engineering.structure.verify",
    "engineering.git.status",
    "engineering.git.diff",
    "engineering.git.commit",
    "engineering.git.push",
})

MUTATING_ENGINEERING_CAPABILITIES = frozenset({
    "engineering.repo.apply",
    "engineering.git.commit",
    "engineering.git.push",
})

READ_ONLY_ENGINEERING_CAPABILITIES = frozenset(
    ENGINEERING_CAPABILITIES - MUTATING_ENGINEERING_CAPABILITIES
)

_ALLOWED_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".html", ".css", ".md", ".swift", ".sh",
}
_DENIED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".maryv2",
    "data", "secrets", ".secrets",
}
_DENIED_NAMES = {
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
}
_MAX_FILE_BYTES = 240_000
_MAX_RESULT_CHARS = 48_000


def discover_engineering_repository() -> Path | None:
    explicit = os.getenv("MARY_ENGINEERING_REPO_ROOT", "").strip()
    candidates = [Path(explicit).expanduser()] if explicit else [Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if (resolved / ".git").exists() and (resolved / "mary").exists():
            return resolved
    return None


def engineering_capability_descriptors(permissions: Any) -> list[CapabilityDescriptor]:
    root = discover_engineering_repository()
    if root is None:
        return []

    model_status: dict[str, Any] = {}
    try:
        provider = LocalRuntimeProvider(role="general")
        model_status = dict(provider.runtime_status() or {})
    except Exception:
        model_status = {}
    model_ready = bool(model_status.get("available"))
    runtime = str(model_status.get("runtime") or "")[:64]
    model = str(model_status.get("model") or "")[:160]

    output: list[CapabilityDescriptor] = []
    for name in sorted(ENGINEERING_CAPABILITIES):
        mutating = name in MUTATING_ENGINEERING_CAPABILITIES
        needs_model = name == "engineering.repair.plan"
        push_enabled = str(
            os.getenv("MARY_ENGINEERING_PUSH_ENABLED", "")
        ).strip().lower() in {"1", "true", "yes", "on"}
        available = bool(
            model_ready if needs_model
            else push_enabled if name == "engineering.git.push"
            else True
        )
        output.append(CapabilityDescriptor(
            name=name,
            available=available,
            private=True,
            local=True,
            cost="local",
            latency="background" if "tests." in name or needs_model else "interactive",
            readiness="ready" if available else "unavailable",
            metadata={
                "worker": "bounded_engineering",
                "proposal_only_planning": True,
                "workspace_isolated_tests": True,
                "mutates_repository": mutating,
                "execution_authorized": bool(permissions.is_allowed(name)),
                "generic_shell": False,
                "network_policy": "Core exposes no network command; local test process inherits node OS policy",
                "local_model_required": needs_model,
                "push_requires_environment_opt_in": name == "engineering.git.push",
                "runtime": runtime if needs_model else "",
                "model": model if needs_model else "",
            },
        ))
    return output


def _clean_text(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _safe_relpath(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("Engineering path must be workspace-relative.")
    path = Path(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Engineering path contains an unsafe segment.")
    if any(part.lower() in _DENIED_PARTS for part in path.parts):
        raise ValueError("Engineering path is outside the bounded source workspace.")
    if path.name.lower() in _DENIED_NAMES:
        raise ValueError("Secret/config credential files are excluded from engineering tasks.")
    if path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported engineering file type: {path.suffix}")
    return path.as_posix()


def _sanitize_change(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Engineering change must be an object.")
    path = _safe_relpath(raw.get("path"))
    content = str(raw.get("content") or raw.get("proposed_content") or "")
    raw_edits = raw.get("edits")
    edits: list[dict[str, str]] = []
    if isinstance(raw_edits, list):
        if len(raw_edits) > 12:
            raise ValueError("Engineering change may contain at most 12 exact edits.")
        for item in raw_edits:
            if not isinstance(item, dict):
                raise ValueError("Engineering edit must be an object.")
            old = str(item.get("old") or "")
            new = str(item.get("new") or "")
            if not old:
                raise ValueError("Engineering exact edit requires non-empty old text.")
            if len(old) > 20_000 or len(new) > 40_000:
                raise ValueError("Engineering exact edit exceeds bounded size.")
            edits.append({"old": old, "new": new})
    if not content and not edits:
        raise ValueError("Engineering change requires full content or exact edits.")
    if len(content) > 300_000:
        raise ValueError("Engineering change exceeds bounded content size.")
    expected = str(raw.get("expected_sha256") or "").strip().lower()
    if expected and not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("expected_sha256 must be a SHA-256 hex digest.")
    return {
        "path": path,
        "content": content,
        "edits": edits,
        "expected_sha256": expected,
    }


def sanitize_engineering_task_args(capability: str, args: dict[str, Any] | None) -> dict[str, Any]:
    name = str(capability or "").strip().lower()
    if name not in ENGINEERING_CAPABILITIES:
        raise ValueError(f"Unsupported engineering capability: {name}")
    values = dict(args or {})

    if name in {"engineering.repo.inspect", "engineering.repair.plan"}:
        task = _clean_text(values.get("task") or values.get("query"), 2000)
        if not task:
            raise ValueError(f"{name} requires a task.")
        max_files = max(1, min(12, int(values.get("max_files", 6) or 6)))
        return {"task": task, "max_files": max_files}

    if name == "engineering.patch.propose":
        raw_changes = values.get("changes")
        if not isinstance(raw_changes, list) or not raw_changes:
            raise ValueError(f"{name} requires a non-empty changes array.")
        if len(raw_changes) > 12:
            raise ValueError("Engineering task may change at most 12 files.")
        return {"changes": [_sanitize_change(item) for item in raw_changes]}

    if name == "engineering.repo.apply":
        proposal_id = _clean_text(values.get("proposal_id"), 120)
        if not proposal_id or not proposal_id.startswith("engineering_proposal_"):
            raise ValueError(
                "engineering.repo.apply requires the exact node-local proposal_id "
                "returned by engineering.repair.plan."
            )
        return {"proposal_id": proposal_id}

    if name == "engineering.git.commit":
        message = _clean_text(values.get("message") or "MaryV2 bounded repair", 120)
        if not message:
            message = "MaryV2 bounded repair"
        return {"message": message}

    if name == "engineering.git.push":
        commit_sha = str(values.get("commit_sha") or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise ValueError("engineering.git.push requires the exact 40-character commit SHA.")
        return {"commit_sha": commit_sha}

    if name == "engineering.tests.targeted":
        raw_paths = values.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("engineering.tests.targeted requires test paths.")
        paths: list[str] = []
        for item in raw_paths[:12]:
            path = _safe_relpath(item)
            if not path.startswith("tests/") or not path.endswith(".py"):
                raise ValueError("Targeted tests must be Python files under tests/.")
            paths.append(path)
        return {"paths": paths}

    return {}


def sanitize_engineering_result(capability: str, result: dict[str, Any] | None) -> dict[str, Any]:
    values = dict(result or {})
    allowed = {
        "ok", "capability", "summary", "base_sha", "files", "changes", "diff",
        "status", "checks", "stdout", "stderr", "returncode", "worker",
        "model", "runtime", "warnings", "applied", "proposal_id", "workspace_isolated",
        "commit_sha", "branch", "remote", "pushed",
    }
    output = {key: values[key] for key in allowed if key in values}
    for key in ("summary", "diff", "stdout", "stderr"):
        if key in output:
            output[key] = str(output[key])[:_MAX_RESULT_CHARS]
    if isinstance(output.get("files"), list):
        output["files"] = [str(item)[:240] for item in output["files"][:100]]
    if isinstance(output.get("changes"), list):
        safe_changes = []
        for raw in output["changes"][:12]:
            if not isinstance(raw, dict):
                continue
            safe_changes.append({
                "path": str(raw.get("path") or "")[:240],
                "expected_sha256": str(raw.get("expected_sha256") or "")[:64],
                "proposed_sha256": str(raw.get("proposed_sha256") or "")[:64],
            })
        output["changes"] = safe_changes
    output["authority"] = "engineering_worker_evidence_only"
    return output


class EngineeringWorker:
    """Typed engineering executor bound to one local MaryV2 checkout."""

    def __init__(self, repository_root: str | Path | None = None) -> None:
        root = Path(repository_root).expanduser() if repository_root else discover_engineering_repository()
        if root is None:
            raise RuntimeError("No MaryV2 engineering repository is configured on this node.")
        self.root = root.resolve()
        if not (self.root / ".git").exists():
            raise RuntimeError("Engineering repository must be a Git checkout.")
        self._proposals: dict[str, dict[str, Any]] = {}
        self._proposal_order: list[str] = []
        self._last_applied_paths: list[str] = []
        self._last_applied_base_sha = ""
        self._last_commit_sha = ""

    def _path(self, relpath: str) -> Path:
        clean = _safe_relpath(relpath)
        path = (self.root / clean).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Engineering path escaped repository root.") from exc
        return path

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _materialize_change(change: dict[str, Any], original: str) -> str:
        content = str(change.get("content") or "")
        if content:
            return content
        proposed = original
        edits = list(change.get("edits") or [])
        if not edits:
            raise ValueError("Engineering change has no materialized content or edits.")
        for edit in edits:
            old = str(dict(edit or {}).get("old") or "")
            new = str(dict(edit or {}).get("new") or "")
            count = proposed.count(old)
            if count != 1:
                raise RuntimeError(
                    "Engineering exact edit is stale or ambiguous "
                    f"(expected one match, found {count})."
                )
            proposed = proposed.replace(old, new, 1)
        return proposed

    def _read(self, relpath: str) -> str:
        path = self._path(relpath)
        if not path.is_file():
            raise FileNotFoundError(relpath)
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError(f"Engineering file exceeds {_MAX_FILE_BYTES} bytes: {relpath}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _git_executable() -> str:
        explicit = os.getenv("MARY_ENGINEERING_GIT_BIN", "").strip()
        if explicit:
            path = Path(explicit).expanduser()
            if path.is_file():
                return str(path)
            raise RuntimeError("MARY_ENGINEERING_GIT_BIN does not point to a Git executable.")

        resolved = shutil.which("git")
        if resolved:
            return resolved

        if os.name == "nt":
            local = Path(os.getenv("LOCALAPPDATA", "")).expanduser()
            if local.exists():
                candidates = sorted(
                    local.glob("GitHubDesktop/app-*/resources/app/git/cmd/git.exe"),
                    reverse=True,
                )
                if candidates:
                    return str(candidates[0])

        raise RuntimeError(
            "Git is required for bounded repository engineering. "
            "Install Git or set MARY_ENGINEERING_GIT_BIN."
        )

    def _git(self, *args: str, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._git_executable(), *args],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
            env=self._safe_env(),
        )

    @staticmethod
    def _safe_env() -> dict[str, str]:
        allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL"}
        return {key: value for key, value in os.environ.items() if key.upper() in allowed}

    def _head_sha(self) -> str:
        run = self._git("rev-parse", "HEAD")
        if run.returncode != 0:
            raise RuntimeError("Unable to resolve the engineering checkout HEAD.")
        value = run.stdout.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise RuntimeError("Engineering checkout returned an invalid HEAD SHA.")
        return value

    def _allowed_branch(self) -> str:
        return os.getenv("MARY_ENGINEERING_ALLOWED_BRANCH", "main").strip() or "main"

    def _allowed_remote(self) -> str:
        return os.getenv("MARY_ENGINEERING_ALLOWED_REMOTE", "origin").strip() or "origin"

    def _current_branch(self) -> str:
        run = self._git("branch", "--show-current")
        if run.returncode != 0:
            raise RuntimeError("Unable to resolve the engineering checkout branch.")
        return run.stdout.strip()

    def _require_clean_checkout(self) -> None:
        run = self._git("status", "--porcelain", "--untracked-files=normal")
        if run.returncode != 0:
            raise RuntimeError("Unable to inspect engineering checkout status.")
        if run.stdout.strip():
            raise RuntimeError(
                "Engineering repair planning requires a clean checkout so Mary never "
                "mixes her proposal with unrelated local changes."
            )

    def _require_allowed_branch(self) -> None:
        branch = self._current_branch()
        allowed = self._allowed_branch()
        if branch != allowed:
            raise RuntimeError(
                f"Engineering repair is restricted to branch {allowed!r}; "
                f"current branch is {branch!r}."
            )

    def git_status(self) -> dict[str, Any]:
        run = self._git("status", "--short", "--untracked-files=normal")
        return {
            "ok": run.returncode == 0,
            "capability": "engineering.git.status",
            "status": run.stdout[:_MAX_RESULT_CHARS],
            "stderr": run.stderr[:4000],
            "returncode": run.returncode,
        }

    def git_diff(self) -> dict[str, Any]:
        run = self._git("diff", "--no-ext-diff", "--")
        return {
            "ok": run.returncode == 0,
            "capability": "engineering.git.diff",
            "diff": run.stdout[:_MAX_RESULT_CHARS],
            "stderr": run.stderr[:4000],
            "returncode": run.returncode,
        }

    def _candidate_files(self, task: str, max_files: int) -> list[str]:
        terms = {
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", task)
            if token.lower() not in {"the", "and", "that", "with", "from", "this", "mary", "fix", "issue"}
        }
        scored: list[tuple[int, str]] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            rel = path.relative_to(self.root)
            if any(part.lower() in _DENIED_PARTS for part in rel.parts):
                continue
            if path.name.lower() in _DENIED_NAMES:
                continue
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")[:20_000].lower()
            except OSError:
                continue
            rel_text = rel.as_posix().lower()
            score = sum(8 for term in terms if term in rel_text) + sum(1 for term in terms if term in text)
            if score:
                scored.append((score, rel.as_posix()))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [path for _, path in scored[:max_files]]

    def inspect(self, task: str, max_files: int = 6) -> dict[str, Any]:
        files = self._candidate_files(task, max_files)
        evidence: list[dict[str, Any]] = []
        for rel in files:
            source = self._read(rel)
            excerpt = source if len(source) <= 9000 else source[:6000] + "\n...<bounded>...\n" + source[-2500:]
            evidence.append({
                "path": rel,
                "sha256": self._sha(source),
                "characters": len(source),
                "excerpt": excerpt,
            })
        base = self._git("rev-parse", "HEAD")
        return {
            "ok": True,
            "capability": "engineering.repo.inspect",
            "summary": f"Selected {len(evidence)} source files for bounded engineering review.",
            "base_sha": base.stdout.strip()[:64] if base.returncode == 0 else "",
            "files": [item["path"] for item in evidence],
            "evidence": evidence,
        }

    def propose(self, changes: list[dict[str, Any]]) -> dict[str, Any]:
        diffs: list[str] = []
        manifest: list[dict[str, str]] = []
        for change in changes:
            rel = _safe_relpath(change["path"])
            original = self._read(rel)
            expected = str(change.get("expected_sha256") or "")
            if expected and expected != self._sha(original):
                raise RuntimeError(f"Source changed since engineering evidence was gathered: {rel}")
            proposed = self._materialize_change(change, original)
            if rel.endswith(".py"):
                ast.parse(proposed, filename=rel)
            diffs.append("".join(difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=rel,
                tofile=f"{rel} (proposed)",
            )))
            manifest.append({
                "path": rel,
                "expected_sha256": self._sha(original),
                "proposed_sha256": self._sha(proposed),
            })
        return {
            "ok": True,
            "capability": "engineering.patch.propose",
            "summary": f"Prepared an exact {len(manifest)}-file proposal. Nothing was written.",
            "changes": manifest,
            "diff": "\n".join(diffs)[:_MAX_RESULT_CHARS],
        }

    def _remember_proposal(
        self,
        changes: list[dict[str, Any]],
        *,
        base_sha: str,
    ) -> str:
        proposal_id = f"engineering_proposal_{uuid4().hex}"
        self._proposals[proposal_id] = {
            "base_sha": str(base_sha or ""),
            "changes": [dict(item) for item in changes],
        }
        self._proposal_order.append(proposal_id)
        while len(self._proposal_order) > 20:
            stale = self._proposal_order.pop(0)
            self._proposals.pop(stale, None)
        return proposal_id

    def apply(
        self,
        changes: list[dict[str, Any]] | None = None,
        *,
        proposal_id: str = "",
    ) -> dict[str, Any]:
        proposal_base_sha = ""
        if proposal_id:
            stored = self._proposals.get(str(proposal_id))
            if stored is None:
                raise KeyError("Engineering proposal is unknown or expired on this node.")
            proposal_base_sha = str(stored.get("base_sha") or "")
            changes = [dict(item) for item in list(stored.get("changes") or [])]
            if proposal_base_sha and self._head_sha() != proposal_base_sha:
                raise RuntimeError(
                    "Refusing engineering apply because repository HEAD changed after the proposal."
                )
        changes = list(changes or [])
        if not changes:
            raise ValueError("No engineering changes were supplied for repository apply.")

        prepared: list[tuple[Path, str, str]] = []
        manifest: list[dict[str, str]] = []
        for change in changes:
            rel = _safe_relpath(change["path"])
            path = self._path(rel)
            original = self._read(rel)
            expected = str(change.get("expected_sha256") or "")
            if not expected:
                raise ValueError("Repository apply requires expected_sha256 for every file.")
            if expected != self._sha(original):
                raise RuntimeError(f"Refusing stale engineering patch: {rel}")
            proposed = self._materialize_change(change, original)
            if rel.endswith(".py"):
                ast.parse(proposed, filename=rel)
            prepared.append((path, proposed, rel))
            manifest.append({
                "path": rel,
                "expected_sha256": expected,
                "proposed_sha256": self._sha(proposed),
            })
        for path, proposed, _rel in prepared:
            path.write_text(proposed, encoding="utf-8")
        self._last_applied_paths = [rel for _path, _proposed, rel in prepared]
        self._last_applied_base_sha = proposal_base_sha or self._head_sha()
        self._last_commit_sha = ""
        if proposal_id:
            self._proposals.pop(str(proposal_id), None)
            self._proposal_order = [
                item for item in self._proposal_order if item != str(proposal_id)
            ]
        return {
            "ok": True,
            "capability": "engineering.repo.apply",
            "summary": f"Applied exactly {len(prepared)} creator-authorized source files. No commit, push, or deploy was performed.",
            "applied": True,
            "proposal_id": str(proposal_id or ""),
            "changes": manifest,
        }

    def commit_last_applied(self, message: str) -> dict[str, Any]:
        if not self._last_applied_paths or not self._last_applied_base_sha:
            raise RuntimeError("No creator-approved engineering apply is waiting to be committed.")

        branch = self._current_branch()
        allowed_branch = self._allowed_branch()
        if branch != allowed_branch:
            raise RuntimeError(
                f"Engineering commit is restricted to branch {allowed_branch!r}; current branch is {branch!r}."
            )
        if self._head_sha() != self._last_applied_base_sha:
            raise RuntimeError(
                "Repository HEAD changed after the engineering proposal; refusing to create a mixed commit."
            )

        remote = self._allowed_remote()
        remote_ref = self._git("rev-parse", f"refs/remotes/{remote}/{allowed_branch}")
        if remote_ref.returncode != 0:
            raise RuntimeError(
                f"Cannot verify {remote}/{allowed_branch}. Fetch/sync the canonical remote "
                "manually before Mary creates a publishable commit."
            )
        tracked = remote_ref.stdout.strip().lower()
        if tracked != self._last_applied_base_sha:
            raise RuntimeError(
                f"Local {allowed_branch} is not synchronized with {remote}/{allowed_branch}; "
                "sync it manually before Mary creates a commit."
            )

        dirty = self._git("status", "--porcelain", "--untracked-files=normal")
        if dirty.returncode != 0:
            raise RuntimeError("Unable to inspect repository changes before commit.")
        allowed_paths = set(self._last_applied_paths)
        for line in dirty.stdout.splitlines():
            path_text = line[3:].strip()
            if " -> " in path_text:
                path_text = path_text.split(" -> ", 1)[1].strip()
            if path_text not in allowed_paths:
                raise RuntimeError(
                    f"Unrelated working-tree change blocks Mary engineering commit: {path_text}"
                )

        add = self._git("add", "--", *self._last_applied_paths)
        if add.returncode != 0:
            raise RuntimeError(add.stderr.strip() or "Git add failed.")

        staged = self._git("diff", "--cached", "--name-only")
        staged_paths = {line.strip() for line in staged.stdout.splitlines() if line.strip()}
        if staged.returncode != 0 or not staged_paths or not staged_paths.issubset(allowed_paths):
            self._git("reset", "--", *self._last_applied_paths)
            raise RuntimeError("Staged files did not match the exact engineering apply set.")

        clean_message = _clean_text(message or "MaryV2 bounded repair", 120)
        commit = self._git("commit", "-m", clean_message, "--", *self._last_applied_paths, timeout=60.0)
        if commit.returncode != 0:
            self._git("reset", "--", *self._last_applied_paths)
            raise RuntimeError(commit.stderr.strip() or "Git commit failed.")

        commit_sha = self._head_sha()
        self._last_commit_sha = commit_sha
        self._last_applied_paths = []
        self._last_applied_base_sha = ""
        return {
            "ok": True,
            "capability": "engineering.git.commit",
            "summary": "Created one local commit containing only the approved engineering apply.",
            "commit_sha": commit_sha,
            "branch": branch,
            "remote": remote,
        }

    def push_last_commit(self, commit_sha: str) -> dict[str, Any]:
        push_enabled = str(
            os.getenv("MARY_ENGINEERING_PUSH_ENABLED", "")
        ).strip().lower() in {"1", "true", "yes", "on"}
        if not push_enabled:
            raise PermissionError(
                "Engineering push also requires MARY_ENGINEERING_PUSH_ENABLED=true on the node."
            )

        expected = str(commit_sha or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", expected):
            raise ValueError("A valid exact commit SHA is required for engineering push.")
        if not self._last_commit_sha or expected != self._last_commit_sha:
            raise RuntimeError("Engineering push may only publish the commit Mary just created.")
        if self._head_sha() != expected:
            raise RuntimeError("Repository HEAD changed after Mary's engineering commit.")

        branch = self._current_branch()
        allowed_branch = self._allowed_branch()
        remote = self._allowed_remote()
        if branch != allowed_branch:
            raise RuntimeError(
                f"Engineering push is restricted to branch {allowed_branch!r}; current branch is {branch!r}."
            )

        status = self._git("status", "--porcelain", "--untracked-files=normal")
        if status.returncode != 0 or status.stdout.strip():
            raise RuntimeError("Engineering push requires a clean working tree.")

        run = self._git(
            "push",
            "--porcelain",
            remote,
            f"{expected}:refs/heads/{allowed_branch}",
            timeout=180.0,
        )
        if run.returncode != 0:
            raise RuntimeError(run.stderr.strip() or "Git push failed.")
        self._last_commit_sha = ""
        return {
            "ok": True,
            "capability": "engineering.git.push",
            "summary": (
                f"Pushed the exact approved engineering commit to {remote}/{allowed_branch}. "
                "Connected CI or deployment services may now react to that branch update."
            ),
            "commit_sha": expected,
            "branch": allowed_branch,
            "remote": remote,
            "pushed": True,
        }


    def _copy_sandbox(self, destination: Path) -> Path:
        """Copy the working tree into a disposable isolated workspace.

        Tests may execute repository code, so they never run in Mary's live
        checkout. Credentials, VCS metadata, virtualenvs, local data, symlinks
        and common generated outputs are excluded. This is workspace isolation,
        not an OS/VM security boundary; test execution remains a separate
        default-deny device permission.
        """

        sandbox_root = destination / "repo"
        denied = {
            ".git", ".venv", "venv", "node_modules", "__pycache__", ".maryv2",
            "data", "secrets", ".secrets", ".pytest_cache", ".mypy_cache",
            "dist", "build", "coverage", "htmlcov",
        }

        def ignore(directory: str, names: list[str]) -> set[str]:
            base = Path(directory)
            return {
                name for name in names
                if name in denied
                or name.startswith("output_")
                or name.endswith(".log")
                or name in _DENIED_NAMES
                or (base / name).is_symlink()
            }

        shutil.copytree(self.root, sandbox_root, ignore=ignore)
        return sandbox_root

    def _run_check(self, argv: list[str], timeout: float) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="mary-engineering-") as temp:
            sandbox = self._copy_sandbox(Path(temp))
            run = subprocess.run(
                argv,
                cwd=sandbox,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
                shell=False,
                env=self._safe_env(),
            )
        return {
            "ok": run.returncode == 0,
            "returncode": run.returncode,
            "stdout": run.stdout[:_MAX_RESULT_CHARS],
            "stderr": run.stderr[:_MAX_RESULT_CHARS],
            "workspace_isolated": True,
        }

    def run_targeted_tests(self, paths: list[str]) -> dict[str, Any]:
        clean = [_safe_relpath(path) for path in paths]
        result = self._run_check([sys.executable, "-m", "pytest", *clean, "-q"], 600.0)
        return {"capability": "engineering.tests.targeted", **result}

    def run_full_tests(self) -> dict[str, Any]:
        result = self._run_check([sys.executable, "-m", "pytest", "-q"], 1200.0)
        return {"capability": "engineering.tests.full", **result}

    def verify_structure(self) -> dict[str, Any]:
        result = self._run_check([sys.executable, "-m", "scripts.verify_repository_structure"], 180.0)
        return {"capability": "engineering.structure.verify", **result}

    def repair_plan(self, task: str, max_files: int = 6) -> dict[str, Any]:
        self._require_clean_checkout()
        self._require_allowed_branch()
        inspection = self.inspect(task, max_files=max_files)
        evidence = list(inspection.get("evidence") or [])
        if not evidence:
            return {
                "ok": False,
                "capability": "engineering.repair.plan",
                "summary": "No bounded source candidates matched the engineering task.",
                "files": [],
            }

        provider = LocalRuntimeProvider(role="general")
        if not provider.is_available():
            raise RuntimeError("No configured local model is ready for the engineering worker.")

        evidence_text = "\n\n".join(
            f"FILE: {item['path']}\nSHA256: {item['sha256']}\n{item['excerpt']}"
            for item in evidence
        )
        prompt = (
            "You are a bounded software-engineering worker. Return ONLY valid JSON, no markdown. "
            "Schema: {\"summary\":\"...\",\"changes\":[{\"path\":\"...\","
            "\"expected_sha256\":\"...\",\"edits\":[{\"old\":\"exact existing text\","
            "\"new\":\"replacement text\"}]}]}. "
            "Prefer small exact edits over full-file rewrites. Every old string must occur exactly once "
            "in the supplied source evidence. Use only files shown below. Make the smallest cohesive fix. "
            "Do not invent credentials, "
            "shell commands, commits, pushes, deployments, or changes to Mary identity/memory. "
            "If no safe fix is supported by the evidence, return an empty changes array.\n\n"
            f"TASK: {task}\n\n{evidence_text}"
        )
        request = GenerationRequest(
            messages=(
                LLMMessage(role="system", content="Return strict JSON engineering evidence only."),
                LLMMessage(role="user", content=prompt),
            ),
            operation=GenerationOperation.TASK_GENERATION.value,
            privacy=GenerationPrivacy.LOCAL_ONLY.value,
            cost_class=GenerationCost.ZERO_LOCAL.value,
            correlation_id=generation_correlation_id("engineering-worker"),
            purpose="bounded_engineering_repair_plan",
            temperature=0.15,
            max_tokens=4096,
        )
        response = provider.generate_constrained(request)
        raw = str(response.content or "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Local engineering model did not return a JSON object.")
        payload = json.loads(raw[start:end + 1])
        raw_changes = payload.get("changes", [])
        if not isinstance(raw_changes, list):
            raise RuntimeError("Local engineering model returned an invalid changes array.")

        evidence_hashes = {item["path"]: item["sha256"] for item in evidence}
        changes: list[dict[str, Any]] = []
        for raw_change in raw_changes[:6]:
            change = _sanitize_change(raw_change)
            if change["content"]:
                raise RuntimeError(
                    "Local engineering repair plans must use bounded exact edits, not full-file rewrites."
                )
            if change["path"] not in evidence_hashes:
                raise RuntimeError(f"Engineering model attempted an out-of-evidence file: {change['path']}")
            change["expected_sha256"] = evidence_hashes[change["path"]]
            changes.append(change)

        proposal = self.propose(changes) if changes else {
            "ok": True,
            "summary": "The engineering worker found no evidence-supported source change.",
            "changes": [],
            "diff": "",
        }
        proposal_id = (
            self._remember_proposal(
                changes,
                base_sha=str(inspection.get("base_sha") or self._head_sha()),
            )
            if changes
            else ""
        )
        return {
            "ok": True,
            "capability": "engineering.repair.plan",
            "summary": _clean_text(payload.get("summary") or proposal.get("summary"), 1200),
            "base_sha": inspection.get("base_sha", ""),
            "proposal_id": proposal_id,
            "files": inspection.get("files", []),
            "changes": proposal.get("changes", []),
            "diff": proposal.get("diff", ""),
            "worker": "bounded_engineering",
            "runtime": provider.runtime_name(),
            "model": str(response.model or provider.model_name())[:160],
            "warnings": [
                "Proposal only: repository files were not written.",
                "Run typed validation/tests before creator-authorized repository apply.",
            ],
        }

    def execute(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        name = str(capability or "").strip().lower()
        values = sanitize_engineering_task_args(name, args)
        if name == "engineering.repo.inspect":
            return self.inspect(values["task"], values["max_files"])
        if name == "engineering.repair.plan":
            return self.repair_plan(values["task"], values["max_files"])
        if name == "engineering.patch.propose":
            return self.propose(values["changes"])
        if name == "engineering.repo.apply":
            return self.apply(
                values.get("changes"),
                proposal_id=str(values.get("proposal_id") or ""),
            )
        if name == "engineering.tests.targeted":
            return self.run_targeted_tests(values["paths"])
        if name == "engineering.tests.full":
            return self.run_full_tests()
        if name == "engineering.structure.verify":
            return self.verify_structure()
        if name == "engineering.git.status":
            return self.git_status()
        if name == "engineering.git.diff":
            return self.git_diff()
        if name == "engineering.git.commit":
            return self.commit_last_applied(values["message"])
        if name == "engineering.git.push":
            return self.push_last_commit(values["commit_sha"])
        raise ValueError(f"No engineering executor exists for {name}.")
