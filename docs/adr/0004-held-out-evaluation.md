# ADR 0004: Held-Out Evaluation Split

**Date:** 2026-06-16
**Status:** Accepted
**Author:** Max Espinoza

## Context

The HarnessX meta-agent can inspect traces and propose harness modifications. Without isolation, the meta-agent could overfit to the benchmark — producing harnesses that perform well on known tasks but fail to generalize.

## Decision

Implement a strict held-out evaluation split: 18 evolution tasks + 6 validation tasks used for candidate selection; 6 held-out test tasks evaluated only after promotion selection and never exposed to the meta-agent.

## Implementation

- **Evolution split (18 tasks)**: Available to the meta-agent for trace analysis and failure diagnosis
- **Validation split (6 tasks)**: Used alongside evolution for candidate scoring; not directly inspected by meta-agent
- **Held-out split (6 tasks, 20%)**: Evaluated only after promotion gate passes; results reported separately

The BenchmarkRunner loads splits from separate YAML files:
- `data/benchmarks/evolution.yaml`
- `data/benchmarks/validation.yaml`
- `data/benchmarks/held_out.yaml`

The meta-agent's `Digester` receives only evolution split traces. The `CandidateRunner` uses evolution + validation for scoring. The held-out report is generated as a completely separate step.

## Enforcement

- CLI enforces: `--split held_out` requires explicit flag, not default
- Database tracks which split each trace belongs to
- Meta-agent pipeline cannot query held_out traces via TraceRepository (query filter enforces this)
