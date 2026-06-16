# Adaptive Harness Foundry — Architecture

## Executive Summary

The Adaptive Harness Foundry (AHF) is a proof-of-concept implementation of the HarnessX architecture using Google ADK Python v2.2+. It demonstrates that agent behavior can be composed, versioned, evaluated, and evolved through **configuration-level mutations only** — without modifying model weights, source code, or training data.

The system wraps an ADK `LlmAgent` in a lifecycle processor pipeline, captures structured traces of every invocation, evaluates outputs deterministically, and uses a constrained meta-agent pipeline to propose bounded harness modifications. A deterministic promotion gate ensures candidates only replace the active harness when they provably improve target metrics without regressing safety or overall performance.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        OPERATOR PLANE                                 │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server (api/)  │  Minimal React UI (ui/)              │  │
│  │  - Harness viewer       │  - Version dashboard                 │  │
│  │  - Benchmark results    │  - Trace inspector                   │  │
│  │  - Promotion control    │  - Rollback control                  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────┐
│                        EVOLUTION PLANE                                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Digester → Planner → Evolver → Critic → Validator → Gate     │  │
│  │  (Constrained meta-agent pipeline, LLM-assisted, determinist-  │  │
│  │   ically gated. Never emits executable Python. Patch linter    │  │
│  │   blocks benchmark leakage, permission expansion, evaluator    │  │
│  │   tampering.)                                                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────┐
│                        EVALUATION PLANE                               │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐  │
│  │  Benchmark Runner            │  │  Deterministic Evaluators    │  │
│  │  - 30 tasks (18/6/6 split)   │  │  - correctness, tool_use,    │  │
│  │  - Fixture-driven tools      │  │    safety, grounding,        │  │
│  │  - Family routing            │  │    efficiency                │  │
│  └──────────────────────────────┘  └──────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────┐
│                        TRACE PLANE                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  TraceRecorder (SQLite + JSONL export)                         │  │
│  │  - Normalized TraceEvents per lifecycle hook                   │  │
│  │  - Raw ADK events where serializable                           │  │
│  │  - Tool call sequences, token usage, latency, errors           │  │
│  │  - Secret redaction before persistence                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────┐
│                        RUNTIME PLANE                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Harness Compiler  →  ADK Agent Assembly  →  Task Runner       │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  LlmAgent                                               │  │  │
│  │  │  ├─ before_model_callback  →  ContextBudgetProcessor    │  │  │
│  │  │  ├─ after_model_callback   →  GroundingCaptureProcessor │  │  │
│  │  │  ├─ before_tool_callback   →  ToolAllowlistProcessor    │  │  │
│  │  │  │                          →  DryRunEnforcementProc.   │  │  │
│  │  │  ├─ after_tool_callback    →  CitationRequirementProc.  │  │  │
│  │  │  ├─ before_agent_callback  →  TaskFamilyContextProc.    │  │  │
│  │  │  └─ after_agent_callback   →  TraceRecorderProcessor    │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────────┐
│                        CATALOG PLANE                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  SQLite Catalog (catalog/)                                     │  │
│  │  - HarnessDefinition (immutable, versioned, hashed)            │  │
│  │  - ProcessorSpec (typed, versioned, capability-declared)       │  │
│  │  - VariantDefinition (inherits + overrides)                    │  │
│  │  - PromotionRecord (parent-child lineage, evidence refs)       │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## Trust Boundaries

| # | Boundary | Protects |
|---|----------|----------|
| TB1 | Evolution plane → Catalog | Catalog immutability — evolved harnesses are new versions, never mutations of existing ones |
| TB2 | Evolution plane → Runtime | No source code emission — only structured YAML/JSON patches |
| TB3 | Evaluation plane → Promotion | Deterministic gate — LLM cannot approve its own output |
| TB4 | Task family → Variant | Variant isolation — task-family-specific configs can't leak into other families |
| TB5 | Meta-agent → Held-out tasks | Held-out split never exposed to evolution — prevents benchmark overfitting |

## Component Architecture

### Catalog Plane

- **HarnessDefinition**: Immutable YAML/JSON configuration with canonical hash (SHA-256 of normalized serialization). Contains model config, agent config, tool policy, processor pipeline assignment.
- **HarnessVersion**: Each edit produces a new version. Version chain: parent → child. Authorship tracked (human vs meta_agent).
- **ProcessorSpec**: Typed processor with declared hook, capability set (read/write permissions), version.
- **VariantDefinition**: Inherits from a base harness, overrides specific fields for a task family.
- **PromotionRecord**: Links candidate to baseline, records gate-by-gate results, stores evidence references.

### Runtime Plane

- **HarnessCompiler**: Validates harness config, resolves processor references, compiles into an ADK `LlmAgent` with attached callbacks.
- **ADKApp**: Factory function creating the ADK application (agent + tools + runner).
- **TaskRunner**: Executes a benchmark task against a harness, collecting trace events.
- **CallbackBridge**: Maps `LifecycleHook` enum to ADK callback types (`before_agent`, `after_agent`, `before_model`, `after_model`, `before_tool`, `after_tool`).

### Trace Plane

- **TraceRecorder**: Writes normalized `TraceEvent` records to SQLite and optionally exports JSONL.
- **TraceRepository**: Query interface for traces by run_id, task_id, harness_id, failure classification.
- **RedactionService**: Strips API keys, PII, and credentials before persistence.

### Evaluation Plane

- **BenchmarkRunner**: Loads benchmark tasks, routes to correct task family variant, executes serially.
- **ScoringEngine**: Computes TaskScore from trace events using deterministic rules.
- **ComparisonEngine**: Diffs two runs at task, family, and global levels.

### Evolution Plane

- **Digester**: Analyzes failed traces, clusters failures, identifies recurring patterns.
- **Planner**: Selects one bounded adaptation objective from observed failures.
- **Evolver**: Generates a `HarnessPatch` using allowed operations (add/remove/replace processor, update config, create variant).
- **Critic**: Reviews patch for safety, benchmark leakage, reward hacking.
- **PatchLinter**: Static analysis rejecting patches with benchmark IDs, expected answers, evaluator tampering.
- **PromotionGate**: Deterministic acceptance policy (all-gates-must-pass).

## Data Flow

```
1. Operator registers baseline harness → Catalog (immutable)
2. CLI triggers benchmark → Runtime compiles ADK agent → runs tasks → Trace Plane records events
3. Evaluation Plane scores traces → produces BenchmarkReport
4. CLI triggers evolve → Evolution Plane reads failed traces → proposes HarnessPatch
5. Patch applied → new candidate harness → benchmark comparison → Promotion Gate
6. If approved → candidate becomes active (new version), previous remains inspectable
```

## Key Design Decisions

1. **Google ADK v2 as runtime engine** — Not wrapped in unnecessary abstractions. The foundry owns configuration, tracing, evaluation, and versioning; ADK handles LLM orchestration. ADK v2 callbacks map cleanly to HarnessX lifecycle hooks.

2. **Configuration-only evolution** — The meta-agent proposes YAML/JSON patches, never Python code. This bounds the adaptation surface to what can be validated and linted.

3. **Deterministic promotion gate** — Implemented as code, not delegated to an LLM. Every criterion is independently testable.

4. **Variant isolation** — Task families get separate harness variants. This limits blast radius of changes and enables family-specific optimization.

5. **Held-out evaluation** — 6 tasks (20%) are never exposed to the meta-agent. This tests generalization.

## Trade-offs

| Decision | Trade-off |
|----------|-----------|
| YAML/JSON patches only | Safe and auditable, but limited adaptation surface vs. code generation |
| Deterministic gate | Provably correct, but cannot express nuanced "better but different" judgments |
| Fake model for testing | CI runs without API keys, but may not catch model-specific behavior |
| SQLite for catalog + traces | Simple deployment, but not multi-writer safe |
| Single-agent architecture | Clearer trace causality, but cannot demonstrate multi-agent evolution |

## Deployment Topology

```
Local development:
  Python venv → ADK → Gemini (live) or fake model (test)
  SQLite database (single file)
  FastAPI dev server (uvicorn)
  CLI via Typer

Docker:
  Dockerfile + docker-compose.yml
  Environment variables for API keys
  Volume mount for SQLite persistence
```
