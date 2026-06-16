"""Harness definition schema models and loading utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from harness_foundry.catalog.hashing import canonical_json as serialize_canonical_json
from harness_foundry.catalog.hashing import config_sha256
from harness_foundry.schema.processor import LifecycleHook


class ModelConfig(BaseModel):
    """Model selection and generation parameters for a harness."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    temperature: float = Field(default=0.0, ge=0)
    maximum_output_tokens: int = Field(default=1024, ge=1)


class AgentConfig(BaseModel):
    """Agent instruction and control settings."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1)
    instruction_append: str | None = None
    maximum_steps: int = Field(..., ge=1)


class ToolPolicy(BaseModel):
    """Tool allowlist policy applied to a harness."""

    model_config = ConfigDict(frozen=True)

    allow: list[str] = Field(default_factory=list)


class ProcessorInstance(BaseModel):
    """Configured processor attachment for a specific hook."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(..., min_length=1)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    config: dict[str, Any] = Field(default_factory=dict)


class HarnessRef(BaseModel):
    """Reference to a specific harness version."""

    model_config = ConfigDict(frozen=True)

    harness_id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")


class AgentOverrides(BaseModel):
    """Allowed agent-level overrides for a variant."""

    model_config = ConfigDict(frozen=True)

    instruction_append: str | None = None


class ProcessorOverrides(BaseModel):
    """Allowed processor-level overrides for a variant.

    Accepts two YAML shapes:
    1. Flat: add_per_hook: {TASK_END: [{type: x, ...}], ...}
    2. Nested: TASK_END: {add: [{type: x, ...}]} (from variant YAML files)
    """

    model_config = ConfigDict(frozen=True)

    add_per_hook: dict[LifecycleHook, list[ProcessorInstance]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _unpack_nested_hooks(cls, data: Any) -> Any:
        """Accept per-hook keys with nested add lists from YAML."""
        if not isinstance(data, dict):
            return data
        # Check if data has known hook keys directly (variant YAML format)
        known_hooks = set(LifecycleHook.__members__.values())
        nested = {k.upper(): v for k, v in data.items() if k.upper() in known_hooks}
        if nested:
            # Convert: {TASK_END: {add: [...]}} → {add_per_hook: {TASK_END: [...]}}
            result: dict[str, Any] = {}
            for hook_name, hook_data in nested.items():
                if isinstance(hook_data, dict) and "add" in hook_data:
                    result.setdefault("add_per_hook", {})
                    result["add_per_hook"][hook_name] = hook_data["add"]
                elif isinstance(hook_data, list):
                    result.setdefault("add_per_hook", {})
                    result["add_per_hook"][hook_name] = hook_data
            # Keep non-hook keys
            for k, v in data.items():
                if k.upper() not in known_hooks:
                    result[k] = v
            return result
        return data


class VariantOverrides(BaseModel):
    """Allowed override surface for a harness variant."""

    model_config = ConfigDict(frozen=True)

    agent: AgentOverrides | None = None
    processors: ProcessorOverrides | None = None


class HarnessDefinition(BaseModel):
    """Immutable harness definition persisted in the catalog."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    parent_version: str | None = Field(default=None, pattern=r"^\d+\.\d+\.\d+$")
    author: Literal["human", "meta_agent"]
    task_family: str = Field(default="default", min_length=1)
    status: Literal[
        "draft",
        "candidate",
        "accepted",
        "rejected",
        "archived",
        "active",
    ]
    model: ModelConfig
    agent: AgentConfig
    tools: ToolPolicy
    processors: dict[LifecycleHook, list[ProcessorInstance]] = Field(default_factory=dict)

    @field_validator("processors", mode="before")
    @classmethod
    def _normalize_processor_hook_keys(cls, value: dict[Any, Any]) -> Any:
        """Accept both snake_case and UPPER_CASE hook keys; always store as uppercase."""
        if not isinstance(value, dict):
            return value
        normalized: dict[str, Any] = {}
        for key, val in value.items():
            upper_key = str(key).upper()
            if upper_key not in LifecycleHook.__members__:
                raise ValueError(f"Unknown lifecycle hook: {key}")
            normalized[upper_key] = val
        return normalized

    @model_validator(mode="after")
    def validate_processor_keys(self) -> HarnessDefinition:
        """Ensure all configured processor hooks are valid lifecycle hooks."""

        invalid_hooks = set(self.processors) - set(LifecycleHook)
        if invalid_hooks:
            invalid = ", ".join(sorted(hook.value for hook in invalid_hooks))
            raise ValueError(f"Invalid processor hook(s): {invalid}")
        return self

    def canonical_json(self) -> str:
        """Return canonical JSON for deterministic hashing and persistence."""

        return serialize_canonical_json(self.model_dump(mode="json"))

    def config_hash(self) -> str:
        """Return the SHA-256 hash of the canonical JSON representation."""

        return config_sha256(self.canonical_json())


class VariantDefinition(HarnessRef):
    """Task-family-specific variant that inherits from a base harness."""

    model_config = ConfigDict(frozen=True)

    task_family: str = Field(..., min_length=1)
    overrides: VariantOverrides = Field(default_factory=VariantOverrides)

    @model_validator(mode="before")
    @classmethod
    def _unpack_extends(cls, data: Any) -> Any:
        """Accept extends.harness_id and extends.version from YAML."""
        if isinstance(data, dict) and "extends" in data:
            extends = data.pop("extends")
            if isinstance(extends, dict):
                if "harness_id" in extends:
                    data.setdefault("harness_id", extends["harness_id"])
                if "version" in extends:
                    data.setdefault("version", extends["version"])
        return data

    def resolve(self, base_definition: HarnessDefinition) -> HarnessDefinition:
        """Apply variant overrides to a base harness definition."""

        if base_definition.id != self.harness_id or base_definition.version != self.version:
            raise ValueError("Variant base reference does not match the supplied harness.")

        resolved = base_definition.model_dump(mode="python")
        resolved["task_family"] = self.task_family

        instruction_append = None
        if self.overrides.agent is not None:
            instruction_append = self.overrides.agent.instruction_append
        if instruction_append is not None:
            resolved["agent"]["instruction_append"] = instruction_append

        if self.overrides.processors is not None and self.overrides.processors.add_per_hook:
            processors = resolved.setdefault("processors", {})
            for hook, additions in self.overrides.processors.add_per_hook.items():
                processors.setdefault(hook, [])
                processors[hook].extend(
                    instance.model_dump(mode="python") for instance in additions
                )

        return HarnessDefinition.model_validate(resolved)


class HarnessLoader:
    """Load immutable harness definitions from YAML or JSON files."""

    @classmethod
    def load(cls, file_path: str | Path) -> HarnessDefinition:
        """Load and validate a harness definition from disk.

        Args:
            file_path: Path to a YAML or JSON file.

        Returns:
            A validated harness definition.
        """

        path = Path(file_path)
        raw_text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(raw_text)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(raw_text)
        else:
            raise ValueError(f"Unsupported harness file extension: {path.suffix}")
        return HarnessDefinition.model_validate(payload)
