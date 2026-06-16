"""Registry of available processor implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness_foundry.processors.base import (
    HOOK_CAPABILITIES,
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
from harness_foundry.processors.tools import (
    DryRunEnforcementProcessor,
    MissingArgumentRepairProcessor,
    RequiredToolSequenceProcessor,
    ToolAllowlistProcessor,
)

if TYPE_CHECKING:
    from harness_foundry.schema.harness import ProcessorInstance
    from harness_foundry.schema.processor import ProcessorSpec


class ProcessorRegistry:
    """Registry of available processor implementations."""

    def __init__(self) -> None:
        self._processors: dict[str, type[BaseProcessor]] = {}

    def register(self, processor_cls: type[BaseProcessor]) -> None:
        """Register a processor implementation class."""

        key = self._key(processor_cls.name, processor_cls.version)
        self._processors[key] = processor_cls

    def get(self, name: str, version: str) -> type[BaseProcessor]:
        """Resolve a processor implementation by name and version."""

        key = self._key(name, version)
        try:
            return self._processors[key]
        except KeyError as exc:
            raise KeyError(f"Unknown processor: {name}@{version}") from exc

    def list_all(self) -> list[ProcessorSpec]:
        """List registered processor specs for catalog use."""

        from harness_foundry.schema.processor import ProcessorSpec

        specs: list[ProcessorSpec] = []
        for processor_cls in sorted(self._processors.values(), key=lambda cls: cls.name):
            for hook in processor_cls.hooks():
                specs.append(
                    ProcessorSpec(
                        name=processor_cls.name,
                        version=processor_cls.version,
                        hook=hook,
                        description=processor_cls.description or processor_cls.name,
                        config_schema=dict(processor_cls.config_schema),
                        declared_reads=set(processor_cls.declared_reads),
                        declared_writes=set(processor_cls.declared_writes),
                        exclusions=list(processor_cls.exclusions),
                        ordering=processor_cls.ordering,
                    )
                )
        return specs

    async def invoke(
        self,
        instance: ProcessorInstance,
        context: ProcessorContext,
        event: ProcessorEvent,
    ) -> ProcessorResult:
        """Instantiate and run a configured processor instance."""

        processor_cls = self.get(instance.type, instance.version)
        processor = processor_cls(config=dict(instance.config))
        result = await processor.process(context, event)
        allowed_capabilities = set(HOOK_CAPABILITIES[context.hook])
        validate_capabilities(result, allowed_capabilities, context.hook)
        return result

    def _key(self, name: str, version: str) -> str:
        return f"{name}@{version}"


registry = ProcessorRegistry()

for _processor_cls in (
    TaskFamilyContextProcessor,
    RelevantFixtureContextProcessor,
    ContextBudgetProcessor,
    ToolAllowlistProcessor,
    RequiredToolSequenceProcessor,
    MissingArgumentRepairProcessor,
    DryRunEnforcementProcessor,
    StepBudgetProcessor,
    RepeatedToolCallProcessor,
    GroundingCaptureProcessor,
    GroundingCheckProcessor,
    TraceRecorderProcessor,
    CitationRequirementProcessor,
    StructuredFinalAnswerProcessor,
):
    registry.register(_processor_cls)
