"""
MaryV2 - Full Mary Runtime Stage

Bridges the generic runtime Pipeline to the complete Mary coordinator.

This stage does not reimplement cognition, memory, conversation, agency,
expression, or any other Mary subsystem. It delegates one input turn to
Mary.process() and exposes the resulting CognitiveCycleResult through the
pipeline.
"""

from __future__ import annotations

from mary.core.mary import Mary
from mary.runtime.pipeline import (
    PipelineContext,
    PipelineStage,
    StageResult,
)


class MaryStage(PipelineStage):
    """
    Pipeline stage that executes one complete MaryV2 interaction.
    """

    def __init__(
        self,
        mary: Mary,
        *,
        name: str = "mary",
        required: bool = True,
        enabled: bool = True,
    ) -> None:
        super().__init__(
            name=name,
            handler=lambda context: None,
            required=required,
            enabled=enabled,
        )

        self.mary = mary

    def process(
        self,
        context: PipelineContext,
    ) -> StageResult:
        """
        Process one string input through the full Mary coordinator.
        """

        if not isinstance(
            context.input_data,
            str,
        ):
            raise TypeError(
                "MaryStage requires string input."
            )

        result = self.mary.process(
            context.input_data
        )

        intent_type = None

        if result.intent is not None:
            intent_type = (
                result.intent.intent_type.value
            )

        return StageResult(
            success=True,
            output=result.final_response,
            values={
                "cognitive_cycle": result,
            },
            metadata={
                "runtime_stage": "mary",
                "intent": intent_type,
                "handled_by": result.metadata.get(
                    "handled_by",
                    "cognition",
                ),
            },
        )
