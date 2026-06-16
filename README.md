# Adaptive Harness Foundry

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

HarnessX-inspired proof of concept: an adaptive agent harness foundry that demonstrates **configuration-level harness evolution** around Google ADK. Agents are composed from typed lifecycle processors, evaluated deterministically, and evolved through structured configuration patches — never source code generation.

> **Status:** Proof of concept. Not production-ready.

## What This Demonstrates

- ✅ Agent harnesses as first-class, versioned, hashed configurations
- ✅ Typed lifecycle processors attached to ADK callbacks
- ✅ Complete structured execution traces (SQLite + JSONL)
- ✅ Deterministic benchmark evaluation (correctness, safety, grounding, efficiency)
- ✅ Meta-agent pipeline: digest traces → plan → propose config patch → validate → evaluate → gate
- ✅ Deterministic promotion gate (code, not LLM)
- ✅ Task-family variant isolation
- ✅ Held-out evaluation split (generalization test)
- ✅ Full provenance: every modification inspectable, reproducible, reversible
- ✅ CLI, API, minimal operator UI, Docker support

## What This Does NOT Do

- ❌ Arbitrary autonomous source-code rewriting (config patches only)
- ❌ Model fine-tuning or GRPO
- ❌ Distributed execution or Kubernetes
- ❌ Production-safe autonomous deployment
- ❌ Sophisticated visual workflow editor

## Quick Start

```bash
# Clone
git clone https://github.com/rmax-ai/adaptive-harness-foundry.git
cd adaptive-harness-foundry

# Install
make install

# Run demo (deterministic mode, no API key needed)
make demo

# Run with live Gemini
export GOOGLE_API_KEY="your-key"
make demo-live
```

## Architecture

```
Catalog (SQLite) → Runtime (ADK) → Trace (SQLite/JSONL) → Evaluation → Evolution → Promotion
```

See [docs/architecture.md](docs/architecture.md) for full architecture.

## CLI Commands

```bash
harnessx-poc catalog list
harnessx-poc benchmark run --harness enterprise-support --version 1.0.0 --split evolution
harnessx-poc evolve propose --harness enterprise-support --version 1.0.0 --run <run-id>
harnessx-poc promote <candidate-id>
harnessx-poc demo
```

## Development

```bash
make install    # Install dependencies
make lint       # Format and lint
make typecheck  # Type check
make test       # Run tests (deterministic only)
make test-live  # Run tests with live Gemini
```

## License

MIT
