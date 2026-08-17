"""
MaryV2 Diagnostics

Provides system-wide health checks for Mary's architecture.

Diagnostics do not modify system state.
They inspect whether Mary's major subsystems exist,
are initialized, and can respond to basic health checks.

The diagnostic system is intentionally conservative:
a subsystem only receives PASS when the corresponding
connection actually exists on the Mary runtime object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""

    name: str
    status: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class MaryDiagnostics:
    """
    System diagnostic service for MaryV2.

    Status values:

        PASS
        WARN
        FAIL

    Diagnostics are read-only. They do not initialize, modify,
    or repair Mary's systems.
    """

    def __init__(self, mary):
        self.mary = mary

    # ============================================================
    # PUBLIC API
    # ============================================================

    def run(self) -> List[DiagnosticResult]:
        """
        Run all available diagnostic checks.
        """

        results: List[DiagnosticResult] = []

        results.extend(self._check_core())
        results.extend(self._check_memory())
        results.extend(self._check_cognition())
        results.extend(self._check_identity())
        results.extend(self._check_character())
        results.extend(self._check_knowledge())
        results.extend(self._check_learning())
        results.extend(self._check_tools())
        results.extend(self._check_agency())
        results.extend(self._check_autonomy())
        results.extend(self._check_conversation())
        results.extend(self._check_expression())
        results.extend(self._check_avatar())
        results.extend(self._check_audio())
        results.extend(self._check_llm())

        return results

    def summary(self) -> Dict[str, Any]:
        """
        Return a machine-readable diagnostic summary.
        """

        results = self.run()

        passed = sum(
            result.status == "PASS"
            for result in results
        )

        warnings = sum(
            result.status == "WARN"
            for result in results
        )

        failed = sum(
            result.status == "FAIL"
            for result in results
        )

        return {
            "healthy": failed == 0,
            "total": len(results),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        }

    def report(self) -> str:
        """
        Return a human-readable diagnostic report.
        """

        results = self.run()
        summary = self._summarize_results(results)

        lines: List[str] = []

        lines.append("=" * 80)
        lines.append("MARY V2 SYSTEM DIAGNOSTIC")
        lines.append("=" * 80)

        for result in results:

            symbol = {
                "PASS": "[OK]",
                "WARN": "[!!]",
                "FAIL": "[XX]",
            }.get(
                result.status,
                "[??]",
            )

            line = (
                f"{symbol} "
                f"{result.status:<4} "
                f"{result.name}"
            )

            if result.message:
                line += f" - {result.message}"

            lines.append(line)

        lines.append("")
        lines.append("-" * 80)
        lines.append("DIAGNOSTIC SUMMARY")
        lines.append("-" * 80)

        lines.append(
            f"Total:    {summary['total']}"
        )

        lines.append(
            f"Passed:   {summary['passed']}"
        )

        lines.append(
            f"Warnings: {summary['warnings']}"
        )

        lines.append(
            f"Failed:   {summary['failed']}"
        )

        lines.append(
            f"Healthy:  {summary['healthy']}"
        )

        lines.append("=" * 80)

        return "\n".join(lines)

    # ============================================================
    # INTERNAL SUMMARY
    # ============================================================

    @staticmethod
    def _summarize_results(
        results: List[DiagnosticResult],
    ) -> Dict[str, Any]:
        """
        Summarize an already-computed diagnostic result set.

        Keeping this separate prevents report() from running the
        entire diagnostic suite twice.
        """

        passed = sum(
            result.status == "PASS"
            for result in results
        )

        warnings = sum(
            result.status == "WARN"
            for result in results
        )

        failed = sum(
            result.status == "FAIL"
            for result in results
        )

        return {
            "healthy": failed == 0,
            "total": len(results),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        }

    # ============================================================
    # GENERIC ATTRIBUTE CHECK
    # ============================================================

    def _check_attribute(
        self,
        name: str,
        attribute: str,
    ) -> DiagnosticResult:
        """
        Check whether Mary has a connected subsystem attribute.
        """

        try:

            value = getattr(
                self.mary,
                attribute,
                None,
            )

            if value is None:

                return DiagnosticResult(
                    name=name,
                    status="FAIL",
                    message=(
                        f"'{attribute}' is not connected"
                    ),
                )

            return DiagnosticResult(
                name=name,
                status="PASS",
                message="connected",
                details={
                    "attribute": attribute,
                    "type": type(value).__name__,
                },
            )

        except Exception as error:

            return DiagnosticResult(
                name=name,
                status="FAIL",
                message=(
                    f"diagnostic error: {error}"
                ),
                details={
                    "attribute": attribute,
                    "error_type": type(error).__name__,
                },
            )

    # ============================================================
    # CORE
    # ============================================================

    def _check_core(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Core Identity",
                "identity",
            ),
            self._check_attribute(
                "Lifecycle",
                "lifecycle",
            ),
        ]

    # ============================================================
    # MEMORY
    # ============================================================

    def _check_memory(self) -> List[DiagnosticResult]:

        results = [
            self._check_attribute(
                "Memory System",
                "memory",
            )
        ]

        memory = getattr(
            self.mary,
            "memory",
            None,
        )

        if memory is None:
            return results

        for name, attribute in (
            ("Working Memory", "working"),
            ("Episodic Memory", "episodic"),
            ("Semantic Memory", "semantic"),
            ("Memory Retrieval", "retrieval"),
            ("Memory Consolidation", "consolidation"),
        ):

            try:

                value = getattr(
                    memory,
                    attribute,
                    None,
                )

                if value is None:

                    results.append(
                        DiagnosticResult(
                            name=name,
                            status="FAIL",
                            message="not connected",
                            details={
                                "attribute": attribute,
                            },
                        )
                    )

                else:

                    results.append(
                        DiagnosticResult(
                            name=name,
                            status="PASS",
                            message="connected",
                            details={
                                "attribute": attribute,
                                "type": type(value).__name__,
                            },
                        )
                    )

            except Exception as error:

                results.append(
                    DiagnosticResult(
                        name=name,
                        status="FAIL",
                        message=(
                            f"diagnostic error: {error}"
                        ),
                        details={
                            "attribute": attribute,
                            "error_type": type(error).__name__,
                        },
                    )
                )

        return results

    # ============================================================
    # COGNITION
    # ============================================================

    def _check_cognition(self) -> List[DiagnosticResult]:

        return self._check_group(
            "Cognition",
            (
                "cognition",
                "reasoning",
                "reflection",
            ),
        )

    # ============================================================
    # IDENTITY
    # ============================================================

    def _check_identity(self) -> List[DiagnosticResult]:

        return self._check_group(
            "Identity",
            (
                "identity",
                "self_model",
                "biography",
            ),
        )

    # ============================================================
    # CHARACTER
    # ============================================================

    def _check_character(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Character Canon",
                "character",
            )
        ]

    # ============================================================
    # KNOWLEDGE
    # ============================================================

    def _check_knowledge(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Knowledge",
                "knowledge",
            )
        ]

    # ============================================================
    # LEARNING
    # ============================================================

    def _check_learning(self) -> List[DiagnosticResult]:

        return self._check_group(
            "Learning",
            (
                "learner",
                "evaluator",
                "researcher",
            ),
        )

    # ============================================================
    # TOOLS
    # ============================================================

    def _check_tools(self) -> List[DiagnosticResult]:
        """Verify the controlled tool manager and core capabilities."""

        manager = getattr(
            self.mary,
            "tools",
            None,
        )

        if manager is None:
            return [
                DiagnosticResult(
                    name="Tools",
                    status="FAIL",
                    message="'tools' is not connected",
                )
            ]

        required_attributes = (
            "registry",
            "filesystem",
            "code",
            "web",
        )
        missing_attributes = [
            attribute
            for attribute in required_attributes
            if getattr(manager, attribute, None) is None
        ]

        registry = getattr(manager, "registry", None)
        required_tools = {
            "filesystem_read",
            "filesystem_list",
            "filesystem_search",
            "code_read",
            "code_analyze",
            "web_search",
        }
        missing_tools: list[str] = []

        if registry is not None:
            missing_tools = sorted(
                name
                for name in required_tools
                if not registry.has(name)
            )

        if missing_attributes or registry is None or missing_tools:
            return [
                DiagnosticResult(
                    name="Tools",
                    status="FAIL",
                    message="controlled tool system is incomplete",
                    details={
                        "missing_attributes": missing_attributes,
                        "missing_tools": missing_tools,
                    },
                )
            ]

        return [
            DiagnosticResult(
                name="Tools",
                status="PASS",
                message="connected",
                details={
                    "registered": len(registry.all()),
                    "workspace_root": str(
                        getattr(manager, "workspace_root", "")
                    ),
                },
            )
        ]

    # ============================================================
    # AGENCY
    # ============================================================

    def _check_agency(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Agency",
                "agency",
            )
        ]

    # ============================================================
    # AUTONOMY
    # ============================================================

    def _check_autonomy(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Autonomy",
                "autonomy",
            )
        ]

    # ============================================================
    # CONVERSATION
    # ============================================================

    def _check_conversation(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Conversation",
                "conversation",
            )
        ]

    # ============================================================
    # EXPRESSION
    # ============================================================

    def _check_expression(self) -> List[DiagnosticResult]:

        return self._check_group(
            "Expression",
            (
                "expression",
                "dialogue",
                "emotion",
                "response",
            ),
        )

    # ============================================================
    # AVATAR
    # ============================================================

    def _check_avatar(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Avatar",
                "avatar",
            )
        ]

    # ============================================================
    # AUDIO
    # ============================================================

    def _check_audio(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "Audio",
                "audio",
            )
        ]

    # ============================================================
    # LLM
    # ============================================================

    def _check_llm(self) -> List[DiagnosticResult]:

        return [
            self._check_attribute(
                "LLM",
                "llm",
            )
        ]

    # ============================================================
    # GROUP HELPER
    # ============================================================

    def _check_group(
        self,
        prefix: str,
        attributes,
    ) -> List[DiagnosticResult]:
        """
        Check several attributes belonging to one subsystem.
        """

        results: List[DiagnosticResult] = []

        for attribute in attributes:

            results.append(
                self._check_attribute(
                    f"{prefix}: {attribute}",
                    attribute,
                )
            )

        return results