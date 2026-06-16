# PYTHON_DEVELOPMENT.md — Day-to-Day Engineering

## Project Conventions

### Async Patterns

```python
# All ADK callbacks and tools should be async
async def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    ...

# Sync functions are auto-wrapped by ADK but prefer explicit async
```

### Pydantic v2 Patterns

```python
from pydantic import BaseModel, ConfigDict, Field

class HarnessDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)  # Immutable after creation

    id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    model: ModelConfig
    agent: AgentConfig
    tools: ToolPolicy
    processors: dict[str, list[ProcessorInstance]]
```

### SQLAlchemy 2 Patterns

```python
from sqlalchemy import String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class HarnessVersion(Base):
    __tablename__ = "harness_versions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    config_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### Dependency Injection

Use explicit constructor injection, not global state:

```python
class HarnessCompiler:
    def __init__(self, catalog: CatalogService, registry: ProcessorRegistry):
        self._catalog = catalog
        self._registry = registry

    def compile(self, harness_id: str, version: str) -> LlmAgent:
        ...
```

### Structured Logging

```python
import structlog
logger = structlog.get_logger()

logger.info("harness_compiled",
    harness_id=harness.id,
    version=harness.version,
    processor_count=len(harness.processors),
)
```

### Error Types

```python
class HarnessError(Exception):
    """Base exception for all harness-related errors."""

class CompilationError(HarnessError):
    """Harness configuration cannot be compiled to an ADK agent."""

class ValidationError(HarnessError):
    """Harness configuration fails schema validation."""

class PromotionError(HarnessError):
    """Candidate failed promotion gate."""
```

### Testing Patterns

```python
# conftest.py — deterministic fake model for testing
import pytest
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

@pytest.fixture
def fake_model_callback():
    """Returns a callback that intercepts model calls and returns canned responses."""
    async def _callback(callback_context, llm_request: LlmRequest) -> LlmResponse | None:
        # Parse the request to determine what canned response to return
        return LlmResponse(content=...)
    return _callback

@pytest.fixture
def harness_agent():
    """Creates an ADK agent with fake model for deterministic testing."""
    ...
```

### Test Organization

```
tests/
├── unit/           # Pure function tests, no ADK
│   ├── test_schema.py
│   ├── test_hashing.py
│   └── test_scoring.py
├── contract/       # Interface contract tests
│   ├── test_processors.py
│   └── test_compilation.py
├── integration/    # ADK integration tests
│   ├── test_agent.py
│   └── test_tracing.py
├── adversarial/    # Security tests
│   └── test_patch_linter.py
└── e2e/            # Full pipeline tests
    └── test_pipeline.py
```
