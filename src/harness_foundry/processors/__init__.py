"""Processor implementations and registry exports."""

from harness_foundry.processors.base import (
    BaseProcessor,
    ProcessorContext,
    ProcessorEvent,
    ProcessorResult,
    validate_capabilities,
)
from harness_foundry.processors.context import (
    ContextBudgetProcessor,
    RelevantFixtureContextProcessor,
    TaskFamilyContextProcessor,
)
from harness_foundry.processors.control import (
    RepeatedToolCallProcessor,
    StepBudgetProcessor,
)
from harness_foundry.processors.grounding import (
    GroundingCaptureProcessor,
    GroundingCheckProcessor,
)
from harness_foundry.processors.observability import (
    CitationRequirementProcessor,
    StructuredFinalAnswerProcessor,
    TraceRecorderProcessor,
)
from harness_foundry.processors.registry import ProcessorRegistry, registry
from harness_foundry.processors.tools import (
    DryRunEnforcementProcessor,
    MissingArgumentRepairProcessor,
    RequiredToolSequenceProcessor,
    ToolAllowlistProcessor,
)

__all__ = [
    "BaseProcessor",
    "CitationRequirementProcessor",
    "ContextBudgetProcessor",
    "DryRunEnforcementProcessor",
    "GroundingCaptureProcessor",
    "GroundingCheckProcessor",
    "MissingArgumentRepairProcessor",
    "ProcessorContext",
    "ProcessorEvent",
    "ProcessorRegistry",
    "ProcessorResult",
    "RelevantFixtureContextProcessor",
    "RepeatedToolCallProcessor",
    "RequiredToolSequenceProcessor",
    "StepBudgetProcessor",
    "StructuredFinalAnswerProcessor",
    "TaskFamilyContextProcessor",
    "ToolAllowlistProcessor",
    "TraceRecorderProcessor",
    "registry",
    "validate_capabilities",
]
