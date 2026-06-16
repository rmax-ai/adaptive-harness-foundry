#!/usr/bin/env bash
# Post-Codex verification script for Adaptive Harness Foundry
# Run after each Codex session to validate changes before committing.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Post-Codex Verification ==="

# 1. Check for new/modified Python files
echo ""
echo "--- Modified files ---"
git diff --name-only 2>/dev/null || find src tests -name '*.py' -newer pyproject.toml

# 2. Syntax check all Python files
echo ""
echo "--- Syntax check ---"
find src tests -name '*.py' | while read f; do
    PYTHONPATH=src python3 -c "import ast; ast.parse(open('$f').read()); print(f'  OK: $f')" 2>&1 || echo "  FAIL: $f"
done

# 3. Import check for main modules
echo ""
echo "--- Import check ---"
modules=(
    "harness_foundry.schema.harness"
    "harness_foundry.schema.processor"
    "harness_foundry.schema.trace"
    "harness_foundry.schema.benchmark"
    "harness_foundry.settings"
    "harness_foundry.tools.customers"
    "harness_foundry.tools.transactions"
    "harness_foundry.tools.policies"
    "harness_foundry.tools.incidents"
    "harness_foundry.tools.registry"
    "harness_foundry.runtime.compiler"
    "harness_foundry.runtime.adk_app"
    "harness_foundry.runtime.runner"
    "harness_foundry.tracing.recorder"
    "harness_foundry.evaluation.runner"
    "harness_foundry.evaluation.evaluators"
    "harness_foundry.evaluation.scoring"
    "harness_foundry.cli"
)
for mod in "${modules[@]}"; do
    if PYTHONPATH=src python3 -c "import $mod" 2>/dev/null; then
        echo "  OK: $mod"
    else
        echo "  MISSING: $mod (may be in progress)"
    fi
done

# 4. Run unit tests
echo ""
echo "--- Unit tests ---"
if [ -d tests/unit ] && ls tests/unit/test_*.py 2>/dev/null; then
    PYTHONPATH=src python3 -m pytest tests/unit/ -v --tb=short -x 2>&1 || echo "  Some tests failed (may be expected during development)"
else
    echo "  No unit tests found"
fi

echo ""
echo "=== Verification complete ==="
