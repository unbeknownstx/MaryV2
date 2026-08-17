"""
MaryV2 - Code Tool

Controlled source-code inspection and development capability.

SECURITY MODEL
--------------

This module intentionally separates:

    CODE READING
        from
    CODE MODIFICATION
        from
    CODE EXECUTION

Reading source code is not execution.

Generating a proposed change is not applying a change.

Writing a change is not permission to execute it.

MaryV2 does NOT provide arbitrary shell execution here.

Operations that modify source code require explicit creator
approval through ToolRegistry.

Arbitrary code execution is intentionally NOT implemented.

If execution is eventually added, it should live behind a separate
sandboxed execution subsystem rather than being added casually to
this module.
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .filesystem import (
    FilesystemClient,
)
from .registry import (
    PermissionLevel,
    ToolRegistry,
)


# ================================================================
# DATA TYPES
# ================================================================


@dataclass
class CodeAnalysis:
    """
    Static analysis information about a source file.
    """

    path: str

    language: str

    valid_syntax: bool

    functions: list[str] = field(
        default_factory=list
    )

    classes: list[str] = field(
        default_factory=list
    )

    imports: list[str] = field(
        default_factory=list
    )

    variables: list[str] = field(
        default_factory=list
    )

    lines: int = 0

    errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "valid_syntax": self.valid_syntax,
            "functions": list(
                self.functions
            ),
            "classes": list(
                self.classes
            ),
            "imports": list(
                self.imports
            ),
            "variables": list(
                self.variables
            ),
            "lines": self.lines,
            "errors": list(
                self.errors
            ),
            "warnings": list(
                self.warnings
            ),
            "metadata": dict(
                self.metadata
            ),
        }


@dataclass
class CodeChange:
    """
    Represents a proposed source-code modification.

    A CodeChange is only a PROPOSAL.

    Creating it does not modify anything.
    """

    path: str

    original: str

    proposed: str

    diff: str

    reason: str = ""

    approved: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "path": self.path,
            "original": self.original,
            "proposed": self.proposed,
            "diff": self.diff,
            "reason": self.reason,
            "approved": self.approved,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# CODE CLIENT
# ================================================================


class CodeClient:
    """
    Controlled source-code capability.

    The client relies on FilesystemClient for workspace boundaries.

    It provides static inspection and proposal generation.

    It does NOT execute arbitrary code.
    """

    def __init__(
        self,
        filesystem: FilesystemClient,
    ) -> None:

        self.filesystem = (
            filesystem
        )

    # ============================================================
    # SOURCE INSPECTION
    # ============================================================

    def read_source(
        self,
        path: str,
    ) -> str:
        """
        Read a source file.

        This uses the filesystem client's read boundary.
        """

        self._validate_source_path(
            path
        )

        return self.filesystem.read_text(
            path
        )

    def analyze(
        self,
        path: str,
    ) -> CodeAnalysis:
        """
        Perform static analysis on a source file.

        Python source is parsed with AST.

        No code is executed.
        """

        self._validate_source_path(
            path
        )

        source = (
            self.filesystem.read_text(
                path
            )
        )

        language = self._detect_language(
            path
        )

        analysis = CodeAnalysis(
            path=path,
            language=language,
            valid_syntax=True,
            lines=len(
                source.splitlines()
            ),
        )

        source_excerpt, source_truncated = self._build_source_evidence(
            source
        )
        analysis.metadata.update({
            "source_grounded": True,
            "source_excerpt": source_excerpt,
            "source_truncated": source_truncated,
            "source_characters": len(source),
        })

        if language != "python":
            analysis.warnings.append(
                "Detailed static analysis "
                "is currently implemented "
                "only for Python."
            )

            return analysis

        try:
            tree = ast.parse(
                source,
                filename=path,
            )

        except SyntaxError as exc:
            analysis.valid_syntax = False

            analysis.errors.append(
                (
                    f"SyntaxError at "
                    f"line {exc.lineno}: "
                    f"{exc.msg}"
                )
            )

            return analysis

        self._collect_ast_information(
            tree,
            analysis,
        )

        analysis.metadata["symbols"] = self._collect_symbol_details(
            tree
        )

        self._collect_basic_warnings(
            source,
            analysis,
        )

        return analysis

    # ============================================================
    # SYNTAX VALIDATION
    # ============================================================

    def validate_python(
        self,
        source: str,
    ) -> CodeAnalysis:
        """
        Validate Python source without executing it.
        """

        analysis = CodeAnalysis(
            path="<memory>",
            language="python",
            valid_syntax=True,
            lines=len(
                str(
                    source
                ).splitlines()
            ),
        )

        try:
            tree = ast.parse(
                str(
                    source
                ),
                filename="<memory>",
            )

        except SyntaxError as exc:
            analysis.valid_syntax = False

            analysis.errors.append(
                (
                    f"SyntaxError at "
                    f"line {exc.lineno}: "
                    f"{exc.msg}"
                )
            )

            return analysis

        self._collect_ast_information(
            tree,
            analysis,
        )

        return analysis

    # ============================================================
    # CHANGE PROPOSALS
    # ============================================================

    def propose_change(
        self,
        path: str,
        proposed_content: str,
        *,
        reason: str = "",
    ) -> CodeChange:
        """
        Create a source-code change proposal.

        IMPORTANT:

        This DOES NOT modify the file.

        It only calculates the proposed difference.
        """

        self._validate_source_path(
            path
        )

        original = (
            self.filesystem.read_text(
                path
            )
        )

        proposed = str(
            proposed_content
        )

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(
                    keepends=True
                ),
                proposed.splitlines(
                    keepends=True
                ),
                fromfile=path,
                tofile=(
                    f"{path} "
                    "(proposed)"
                ),
            )
        )

        return CodeChange(
            path=path,
            original=original,
            proposed=proposed,
            diff=diff,
            reason=str(
                reason
            ).strip(),
            metadata={
                "changes_source": True,
                "requires_creator_approval": True,
            },
        )

    # ============================================================
    # SAFE CHANGE VALIDATION
    # ============================================================

    def validate_change(
        self,
        change: CodeChange,
    ) -> dict[str, Any]:
        """
        Validate a proposed change before it can be considered
        for approval.

        For Python, syntax is checked without execution.
        """

        path = change.path

        language = self._detect_language(
            path
        )

        result: dict[
            str,
            Any,
        ] = {
            "path": path,
            "language": language,
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        if language == "python":

            analysis = (
                self.validate_python(
                    change.proposed
                )
            )

            result[
                "valid"
            ] = analysis.valid_syntax

            result[
                "errors"
            ] = list(
                analysis.errors
            )

            result[
                "warnings"
            ] = list(
                analysis.warnings
            )

        return result

    # ============================================================
    # APPLY CHANGE
    # ============================================================

    def apply_change(
        self,
        change: CodeChange,
    ) -> str:
        """
        Apply a previously proposed source-code change.

        IMPORTANT:

        This method modifies source code.

        It MUST be registered as APPROVAL_REQUIRED.

        This method itself does not accept an approval token.
        ToolRegistry is responsible for controlling whether this
        method can execute.
        """

        validation = (
            self.validate_change(
                change
            )
        )

        if not validation["valid"]:
            errors = validation[
                "errors"
            ]

            raise ValueError(
                "Cannot apply invalid "
                "source code: "
                + "; ".join(
                    errors
                )
            )

        return self.filesystem.write_text(
            change.path,
            change.proposed,
            overwrite=True,
        )

    # ============================================================
    # DIFF
    # ============================================================

    def diff(
        self,
        path: str,
        proposed_content: str,
    ) -> str:
        """
        Return a unified diff without modifying anything.
        """

        change = (
            self.propose_change(
                path,
                proposed_content,
            )
        )

        return change.diff

    # ============================================================
    # LANGUAGE DETECTION
    # ============================================================

    @staticmethod
    def _detect_language(
        path: str,
    ) -> str:
        """
        Detect source language from file extension.
        """

        suffix = (
            Path(path)
            .suffix
            .lower()
        )

        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".html": "html",
            ".css": "css",
            ".toml": "toml",
            ".sql": "sql",
            ".sh": "shell",
        }

        return mapping.get(
            suffix,
            "unknown",
        )

    # ============================================================
    # AST ANALYSIS
    # ============================================================

    @staticmethod
    def _collect_ast_information(
        tree: ast.AST,
        analysis: CodeAnalysis,
    ) -> None:
        """
        Collect basic Python structure information.
        """

        for node in ast.walk(
            tree
        ):

            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                analysis.functions.append(
                    node.name
                )

            elif isinstance(
                node,
                ast.ClassDef,
            ):
                analysis.classes.append(
                    node.name
                )

            elif isinstance(
                node,
                ast.Import,
            ):
                for alias in (
                    node.names
                ):
                    analysis.imports.append(
                        alias.name
                    )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                module = (
                    node.module
                    or ""
                )

                analysis.imports.append(
                    module
                )

            elif isinstance(
                node,
                ast.Assign,
            ):
                for target in (
                    node.targets
                ):
                    if isinstance(
                        target,
                        ast.Name,
                    ):
                        analysis.variables.append(
                            target.id
                        )

            elif isinstance(
                node,
                ast.AnnAssign,
            ):
                if isinstance(
                    node.target,
                    ast.Name,
                ):
                    analysis.variables.append(
                        node.target.id
                    )

        analysis.functions = sorted(
            set(
                analysis.functions
            )
        )

        analysis.classes = sorted(
            set(
                analysis.classes
            )
        )

        analysis.imports = sorted(
            set(
                analysis.imports
            )
        )

        analysis.variables = sorted(
            set(
                analysis.variables
            )
        )

    # ============================================================
    # SOURCE GROUNDING EVIDENCE
    # ============================================================

    @staticmethod
    def _build_source_evidence(
        source: str,
        *,
        max_chars: int = 10_000,
    ) -> tuple[str, bool]:
        """
        Return bounded source evidence for grounded code explanation.

        Static AST structure alone is not enough to support claims about
        implementation behavior.  When a file is too large, preserve both
        the beginning and end so imports/initialization and later persistence
        or status methods remain visible to reasoning.
        """

        text = str(source)
        limit = max(1_000, int(max_chars))

        if len(text) <= limit:
            return text, False

        marker = (
            "\n\n... [middle of source omitted by bounded code tool] ...\n\n"
        )
        available = max(1_000, limit - len(marker))
        head_budget = int(available * 0.6)
        tail_budget = available - head_budget

        head = text[:head_budget]
        if "\n" in head:
            head = head.rsplit("\n", 1)[0]

        tail = text[-tail_budget:]
        if "\n" in tail:
            tail = tail.split("\n", 1)[-1]

        return head + marker + tail, True

    @staticmethod
    def _collect_symbol_details(
        tree: ast.AST,
    ) -> list[dict[str, Any]]:
        """Return exact symbol names and source line ranges from the AST."""

        details: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                details.append({
                    "kind": "class",
                    "name": node.name,
                    "line": getattr(node, "lineno", None),
                    "end_line": getattr(node, "end_lineno", None),
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                details.append({
                    "kind": (
                        "async_function"
                        if isinstance(node, ast.AsyncFunctionDef)
                        else "function"
                    ),
                    "name": node.name,
                    "line": getattr(node, "lineno", None),
                    "end_line": getattr(node, "end_lineno", None),
                    "arguments": [
                        argument.arg
                        for argument in (
                            list(node.args.posonlyargs)
                            + list(node.args.args)
                            + list(node.args.kwonlyargs)
                        )
                    ],
                })

        details.sort(
            key=lambda item: (
                item.get("line") is None,
                item.get("line") or 0,
                str(item.get("name", "")),
            )
        )
        return details

    # ============================================================
    # BASIC STATIC WARNINGS
    # ============================================================

    @staticmethod
    def _collect_basic_warnings(
        source: str,
        analysis: CodeAnalysis,
    ) -> None:
        """
        Detect a few potentially dangerous Python constructs.

        These are warnings only.

        This is NOT a security sandbox.
        """

        patterns = {
            r"\beval\s*\(": (
                "Uses eval()."
            ),
            r"\bexec\s*\(": (
                "Uses exec()."
            ),
            r"\bos\.system\s*\(": (
                "Uses os.system()."
            ),
            r"\bsubprocess\b": (
                "Uses subprocess."
            ),
            r"\bsocket\b": (
                "Uses socket functionality."
            ),
            r"\b__import__\s*\(": (
                "Uses dynamic imports."
            ),
            r"\bopen\s*\(": (
                "Uses direct file opening."
            ),
        }

        for pattern, warning in (
            patterns.items()
        ):
            if re.search(
                pattern,
                source,
            ):
                analysis.warnings.append(
                    warning
                )

    # ============================================================
    # PATH VALIDATION
    # ============================================================

    @staticmethod
    def _validate_source_path(
        path: str,
    ) -> None:
        """
        Validate that a path looks like a source-code path.

        The actual workspace boundary is enforced by
        FilesystemClient.
        """

        if not str(
            path
        ).strip():
            raise ValueError(
                "Source path cannot "
                "be empty."
            )

        suffix = (
            Path(path)
            .suffix
            .lower()
        )

        allowed = {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".html",
            ".css",
            ".sql",
            ".sh",
            ".md",
        }

        if suffix not in allowed:
            raise ValueError(
                f"Unsupported source "
                f"file type: {suffix}"
            )

    # ============================================================
    # TOOL REGISTRATION
    # ============================================================

    def register_tools(
        self,
        registry: ToolRegistry,
    ) -> None:
        """
        Register code capabilities.

        Inspection and static validation are SAFE.

        Source-code modification requires creator approval.

        Arbitrary execution is intentionally absent.
        """

        # --------------------------------------------------------
        # SAFE OPERATIONS
        # --------------------------------------------------------

        registry.register(
            name="code_read",
            description=(
                "Read source code from a "
                "permitted workspace."
            ),
            function=self.read_source,
            category="code",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "source_read",
                "execution": False,
            },
        )

        registry.register(
            name="code_analyze",
            description=(
                "Statically analyze source "
                "code without executing it."
            ),
            function=self.analyze,
            category="code",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "static_analysis",
                "execution": False,
            },
        )

        registry.register(
            name="code_validate_python",
            description=(
                "Validate Python syntax "
                "without executing code."
            ),
            function=self.validate_python,
            category="code",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "source": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "syntax_validation",
                "execution": False,
            },
        )

        registry.register(
            name="code_diff",
            description=(
                "Generate a proposed source "
                "code diff without modifying "
                "the file."
            ),
            function=self.diff,
            category="code",
            version="1.0",
            permission_level=(
                PermissionLevel.SAFE
            ),
            external_access=False,
            mutates_state=False,
            parameters={
                "path": {
                    "type": "string",
                    "required": True,
                },
                "proposed_content": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "change_proposal",
                "execution": False,
            },
        )

        # --------------------------------------------------------
        # APPROVAL-GATED OPERATIONS
        # --------------------------------------------------------

        registry.register(
            name="code_apply_change",
            description=(
                "Apply an explicitly approved "
                "source-code change."
            ),
            function=self.apply_change,
            category="code",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=False,
            mutates_state=True,
            creator_sensitive=True,
            parameters={
                "change": {
                    "type": "object",
                    "required": True,
                },
            },
            metadata={
                "operation": "source_modification",
                "requires_creator_approval": True,
                "self_modification": True,
            },
        )

        # --------------------------------------------------------
        # INTENTIONALLY NO EXECUTION TOOL
        # --------------------------------------------------------
        #
        # Do NOT register:
        #
        #     code_execute
        #     shell_execute
        #     python_execute
        #
        # Those capabilities require a separate sandboxed
        # architecture.
        # --------------------------------------------------------


# ================================================================
# FACTORY
# ================================================================


def create_code_client(
    filesystem: FilesystemClient,
) -> CodeClient:
    """
    Create a code client using a controlled filesystem.
    """

    return CodeClient(
        filesystem=filesystem
    )


def register_code_tools(
    registry: ToolRegistry,
    filesystem: FilesystemClient,
) -> CodeClient:
    """
    Create a code client and register its capabilities.
    """

    client = create_code_client(
        filesystem
    )

    client.register_tools(
        registry
    )

    return client