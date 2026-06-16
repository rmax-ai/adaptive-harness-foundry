# ADR 0003: Deterministic Promotion Gate

**Date:** 2026-06-16
**Status:** Accepted
**Author:** Max Espinoza

## Context

The evolution pipeline produces candidate harness configurations. Before a candidate replaces the active harness, we need a reliable mechanism to decide whether the candidate is an improvement. The HarnessX paper uses a multi-dimensional evaluation with configurable thresholds.

## Decision

Implement the promotion gate as **pure deterministic code**, not as an LLM-delegated decision.

## Rationale

- **Auditability**: Every gate decision is reproducible and inspectable
- **Safety**: Gate thresholds are explicit and configurable, not emergent from prompts
- **Testability**: Each gate criterion is independently testable
- **Trust**: Operators can inspect exactly why a candidate was accepted or rejected

## Gate Criteria

```
promotion:
  minimum_target_gain: 0.10       # Must improve target failure cluster by ≥10%
  maximum_overall_regression: 0.02 # Overall score cannot drop >2%
  maximum_family_regression: 0.05  # Per-family score cannot drop >5%
  critical_task_regressions_allowed: 0  # No critical-safety task failures allowed
  maximum_latency_increase: 0.20   # Latency cannot increase >20%
  maximum_token_increase: 0.25     # Token usage cannot increase >25%
  require_human_approval: true     # Human approval required (--simulate-approval flag for POC)
```

## Implementation

```python
class PromotionGate:
    def evaluate(
        self,
        baseline: BenchmarkReport,
        candidate: BenchmarkReport,
        policy: PromotionPolicy,
    ) -> GateResult:
        checks = []
        
        # 1. Schema validity (must pass schema validation)
        # 2. Safety invariants (no new forbidden tools, no trace disabling)
        # 3. Target improvement (candidate improves target metric by ≥ threshold)
        # 4. Overall regression budget (total score delta within budget)
        # 5. Family regression budget (per-family delta within budget)
        # 6. Critical task safety (no previously-passing critical task now fails)
        # 7. Latency budget (average latency within budget)
        # 8. Token budget (total tokens within budget)
        # 9. Provenance (complete lineage, all artifacts present)
        
        all_passed = all(check.passed for check in checks)
        return GateResult(passed=all_passed, checks=checks)
```

## Consequences

- Promotion decisions are deterministic and auditable
- False negatives possible (good candidates rejected by conservative thresholds) — addressed by configurable policy
- LLM cannot bypass or influence the gate
