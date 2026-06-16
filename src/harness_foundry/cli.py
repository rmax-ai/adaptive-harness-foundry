"""Typer CLI entry point for Adaptive Harness Foundry."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

import typer

try:
    from harness_foundry.settings import DATABASE_URL, GOOGLE_API_KEY, get_settings
except ImportError:
    from harness_foundry.settings import DATABASE_URL, GOOGLE_API_KEY

    def get_settings() -> dict[str, Any]:
        """Return a minimal settings snapshot when no helper is defined."""

        return {"DATABASE_URL": DATABASE_URL}


app = typer.Typer(name="harnessx-poc", help="Adaptive Harness Foundry CLI")

catalog_app = typer.Typer()
app.add_typer(catalog_app, name="catalog")

benchmark_app = typer.Typer()
app.add_typer(benchmark_app, name="benchmark")

traces_app = typer.Typer()
app.add_typer(traces_app, name="traces")

evolve_app = typer.Typer()
app.add_typer(evolve_app, name="evolve")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@catalog_app.command("list")
def catalog_list() -> None:
    """List available harnesses."""

    typer.echo("Not yet implemented — catalog service coming in Phase 2")


@catalog_app.command("show")
def catalog_show(
    harness_id: str,
    version: str | None = typer.Option(None, "--version"),
) -> None:
    """Show harness details."""

    typer.echo(f"Not yet implemented — harness: {harness_id} v{version}")


@benchmark_app.command("run")
def benchmark_run(
    harness: str = typer.Option(..., "--harness"),
    version: str = typer.Option(..., "--version"),
    split: str = typer.Option("evolution", "--split"),
    variant: str | None = typer.Option(None, "--variant"),
) -> None:
    """Run benchmark tasks against a harness."""

    async def _run() -> None:
        from harness_foundry.evaluation.report import render_markdown_report

        repo, _service = await _init_catalog_service()
        harness_def = await _load_harness_definition(repo, harness, version)

        task_family: str | None = None
        if variant is not None:
            variant_def = _load_variant_definition(variant)
            harness_def = variant_def.resolve(harness_def)
            task_family = variant_def.task_family

        runner = _create_benchmark_runner()
        report = await runner.run_benchmark(harness_def, split, task_family=task_family)
        typer.echo(render_markdown_report(report))
        typer.echo(f"\nReport saved. Run ID: {report.run_id}")

    _run_async_command(_run)


@benchmark_app.command("compare")
def benchmark_compare(
    baseline_run: str = typer.Option(..., "--baseline-run"),
    candidate_run: str = typer.Option(..., "--candidate-run"),
) -> None:
    """Compare two benchmark runs."""

    typer.echo(f"Comparing {baseline_run} vs {candidate_run}")


@traces_app.command("show")
def traces_show(trace_id: str) -> None:
    """Show trace details."""

    typer.echo(f"Trace: {trace_id}")


@traces_app.command("export")
def traces_export(
    run_id: str,
    format: str = typer.Option("jsonl", "--format"),
) -> None:
    """Export traces for a run."""

    typer.echo(f"Exporting traces for run {run_id} as {format}")


@evolve_app.command("propose")
def evolve_propose(
    harness: str = typer.Option(..., "--harness"),
    version: str = typer.Option(..., "--version"),
    run: str = typer.Option(..., "--run"),
) -> None:
    """Propose a harness evolution."""

    async def _run() -> None:
        from harness_foundry.evolution import (
            CandidateCritic,
            CandidateEvolver,
            EvolutionPipeline,
            FailurePlanner,
            PatchLinter,
            PromotionGate,
            TraceDigester,
        )

        repo, service = await _init_catalog_service()
        harness_def = await _load_harness_definition(repo, harness, version)
        runner = _create_benchmark_runner()
        pipeline = EvolutionPipeline(
            digester=TraceDigester(),
            planner=FailurePlanner(),
            evolver=CandidateEvolver(),
            critic=CandidateCritic(),
            linter=PatchLinter(),
            catalog=service,
            benchmark_runner=runner,
            promotion_gate=PromotionGate(),
        )
        result = await pipeline.run(harness_def, run)

        typer.echo(f"Evolution status: {result.status}")
        if result.patch is not None:
            typer.echo(f"Patch: {result.patch.operation} target={result.patch.target}")
        if result.lint_violations:
            typer.echo(f"Lint violations: {', '.join(result.lint_violations)}")
        if result.critic_review:
            typer.echo(
                "Critic: "
                f"{result.critic_review.get('decision')} "
                f"(risk={result.critic_review.get('risk_level')})"
            )
        if result.gate_result is not None:
            typer.echo(f"Gate passed: {result.gate_result.passed}")
        if result.candidate_version is not None:
            typer.echo(f"Candidate version: {result.candidate_version}")

    _run_async_command(_run)


@evolve_app.command("evaluate")
def evolve_evaluate(candidate_id: str) -> None:
    """Evaluate a candidate harness."""

    async def _run() -> None:
        from harness_foundry.evaluation import ComparisonEngine
        from harness_foundry.evaluation.report import render_comparison_report

        harness_id, candidate_version = _parse_candidate_ref(candidate_id)
        repo, _service = await _init_catalog_service()
        candidate = await _require_harness(repo, harness_id, candidate_version)
        if candidate.parent_version is None:
            raise typer.BadParameter("Candidate harness is missing parent_version.")

        baseline = await _require_harness(repo, harness_id, candidate.parent_version)
        runner = _create_benchmark_runner()
        baseline_report = await runner.run_benchmark(baseline, "validation")
        candidate_report = await runner.run_benchmark(candidate, "validation")
        comparison = ComparisonEngine().compare(baseline_report, candidate_report)

        typer.echo(render_comparison_report(comparison))

    _run_async_command(_run)


@app.command()
def promote(
    candidate_id: str,
    simulate_approval: bool = typer.Option(False, "--simulate-approval"),
) -> None:
    """Promote a candidate harness (requires passing promotion gate)."""

    async def _run() -> None:
        from harness_foundry.catalog.service import GateResult as CatalogGateResult
        from harness_foundry.evolution import PromotionGate

        harness_id, candidate_version = _parse_candidate_ref(candidate_id)
        repo, service = await _init_catalog_service()
        candidate = await _require_harness(repo, harness_id, candidate_version)
        if candidate.parent_version is None:
            raise typer.BadParameter("Candidate harness is missing parent_version.")

        baseline = await _require_harness(repo, harness_id, candidate.parent_version)
        runner = _create_benchmark_runner()
        baseline_report = await runner.run_benchmark(baseline, "validation")
        candidate_report = await runner.run_benchmark(candidate, "validation")

        gate = PromotionGate()
        gate_result = gate.evaluate(
            baseline=baseline_report,
            candidate=candidate_report,
            simulate_approval=simulate_approval,
        )
        await service.promote_candidate(
            candidate.id,
            candidate.version,
            CatalogGateResult(
                decision="accepted" if gate_result.passed else "rejected",
                summary=gate_result.model_dump(mode="python"),
                patch={},
            ),
        )

        typer.echo(f"Promotion passed: {gate_result.passed}")
        for check in gate_result.checks:
            typer.echo(f"- {check.name}: {check.passed} ({check.detail})")

    _run_async_command(_run)


@app.command()
def rollback(
    harness: str = typer.Option(..., "--harness"),
    to_version: str = typer.Option(..., "--to-version"),
) -> None:
    """Rollback to a previous harness version."""

    async def _run() -> None:
        repo, _service = await _init_catalog_service()
        target = await _require_harness(repo, harness, to_version)
        active = await repo.get_active_harness(harness)

        if active is not None and active.version != target.version:
            await repo.update_harness(active.model_copy(update={"status": "archived"}))
        await repo.update_harness(target.model_copy(update={"status": "active"}))
        typer.echo(f"Rolled back {harness} to v{to_version}")

    _run_async_command(_run)


@app.command()
def validate(config_path: str) -> None:
    """Validate a harness configuration file."""

    typer.echo(f"Validating: {config_path}")
    try:
        from harness_foundry.schema.harness import HarnessLoader

        harness = HarnessLoader.load(config_path)
        typer.echo(f"✓ Valid: {harness.id} v{harness.version}")
    except Exception as exc:
        typer.echo(f"✗ Invalid: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command(name="compile")
def compile_cmd(config_path: str) -> None:
    """Compile a harness configuration to ADK agent."""

    typer.echo(f"Compiling: {config_path}")
    typer.echo("Not yet implemented — compiler wiring is coming in a future batch")


@app.command()
def demo(simulate_approval: bool = typer.Option(True, "--simulate-approval")) -> None:
    """Run the complete proof-of-concept demo."""

    async def _run() -> None:
        import yaml  # type: ignore[import-untyped]

        from harness_foundry.evaluation.report import render_markdown_report
        from harness_foundry.evolution import (
            CandidateCritic,
            CandidateEvolver,
            EvolutionPipeline,
            FailurePlanner,
            PatchLinter,
            PromotionGate,
            TraceDigester,
        )
        from harness_foundry.schema.harness import HarnessLoader, VariantDefinition

        typer.echo("=" * 60)
        typer.echo("Adaptive Harness Foundry — Complete Demo")
        typer.echo("=" * 60)

        demo_db_path = Path(tempfile.mkdtemp(prefix="harness-foundry-demo-")) / "catalog.sqlite3"
        repo, service = await _init_catalog_service(db_url=f"sqlite:///{demo_db_path}")
        harness = HarnessLoader.load(PROJECT_ROOT / "configs" / "baseline.yaml")
        await _register_if_missing(repo, service, harness)
        typer.echo(
            "\n1. Registered baseline: "
            f"{harness.id} v{harness.version} (hash: {harness.config_hash()[:12]}...)"
        )

        runner = _create_benchmark_runner()
        if not _has_live_model_access():
            typer.echo("   Running in fake-model mode because GOOGLE_API_KEY is unset.")

        typer.echo("\n2. Running baseline benchmark (evolution split)...")
        baseline_report = await runner.run_benchmark(harness, "evolution")
        typer.echo(
            f"   Baseline: {baseline_report.total_score:.2f} "
            f"({baseline_report.pass_rate:.0%} pass rate)"
        )

        typer.echo("\n3. Testing task-family variants...")
        variant_results: dict[str, Any] = {}
        for variant_name in ["policy_question", "account_lookup", "incident_triage"]:
            variant_path = PROJECT_ROOT / "configs" / "variants" / f"{variant_name}.yaml"
            variant_data = yaml.safe_load(variant_path.read_text(encoding="utf-8"))
            variant_def = VariantDefinition.model_validate(variant_data)
            resolved = variant_def.resolve(harness)
            report = await runner.run_benchmark(
                resolved,
                "evolution",
                task_family=variant_def.task_family,
            )
            variant_results[variant_name] = report
            typer.echo(f"   {variant_name}: {report.total_score:.2f}")

        typer.echo("\n4. Running validation benchmark...")
        val_report = await runner.run_benchmark(harness, "validation")
        typer.echo(f"   Validation: {val_report.total_score:.2f}")

        typer.echo("\n5. Running evolution pipeline...")
        pipeline = EvolutionPipeline(
            digester=TraceDigester(),
            planner=FailurePlanner(),
            evolver=CandidateEvolver(),
            critic=CandidateCritic(),
            linter=PatchLinter(),
            catalog=service,
            benchmark_runner=runner,
            promotion_gate=PromotionGate(),
        )
        result = await pipeline.run(harness, baseline_report.run_id)
        if result.patch is not None:
            typer.echo(f"   Proposed patch: {result.patch.operation} on {result.patch.target}")
        typer.echo(f"   Lint: {'clean' if not result.lint_violations else result.lint_violations}")
        typer.echo(
            "   Critic: "
            f"{result.critic_review.get('decision')} "
            f"(risk={result.critic_review.get('risk_level')})"
        )
        if result.gate_result is not None:
            typer.echo(f"   Gate: {'PASSED' if result.gate_result.passed else 'FAILED'}")
        elif result.status == "rejected_pre_evaluation":
            typer.echo("   Gate: SKIPPED")

        if simulate_approval and result.candidate_report is not None:
            approval_gate = PromotionGate().evaluate(
                baseline=result.baseline_report or baseline_report,
                candidate=result.candidate_report,
                simulate_approval=True,
            )
            typer.echo(
                f"   Simulated approval gate: {'PASSED' if approval_gate.passed else 'FAILED'}"
            )

        typer.echo("\n6. Running held-out evaluation...")
        heldout_report = await runner.run_benchmark(harness, "held_out")
        typer.echo(render_markdown_report(heldout_report))

        typer.echo("\n" + "=" * 60)
        typer.echo("DEMO COMPLETE")
        typer.echo(f"Baseline score: {baseline_report.total_score:.2f}")
        typer.echo(f"Validation score: {val_report.total_score:.2f}")
        typer.echo(f"Held-out score: {heldout_report.total_score:.2f}")
        variant_summary = ", ".join(
            f"{name}: {report.total_score:.2f}" for name, report in variant_results.items()
        )
        typer.echo(f"Variants: {{ {variant_summary} }}")
        typer.echo("=" * 60)
        typer.echo("Demo complete.")

    _run_async_command(_run)


@app.command()
def api() -> None:
    """Start the operator API server."""

    typer.echo(f"Starting API server on http://localhost:8000 using {DATABASE_URL}")
    try:
        import uvicorn

        from harness_foundry.api.app import create_app

        api_app = create_app()
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    uvicorn.run(api_app, host="0.0.0.0", port=8000)


def _run_async_command(factory: Any) -> None:
    """Run an async CLI command with consistent error handling."""

    try:
        asyncio.run(factory())
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


async def _init_catalog_service(db_url: str | None = None) -> tuple[Any, Any]:
    """Initialize and return the catalog repository and service."""

    from harness_foundry.catalog.repository import CatalogRepository
    from harness_foundry.catalog.service import CatalogService

    repo = CatalogRepository(db_url=db_url)
    await repo.init()
    return repo, CatalogService(repo)


async def _load_harness_definition(repo: Any, harness: str, version: str) -> Any:
    """Load a harness from the catalog first, then fall back to disk."""

    from harness_foundry.schema.harness import HarnessLoader

    catalog_harness = await repo.get_harness(harness, version)
    if catalog_harness is not None:
        return catalog_harness
    return HarnessLoader.load(_resolve_harness_path(harness))


async def _require_harness(repo: Any, harness_id: str, version: str) -> Any:
    """Load a harness from the catalog and raise if it is missing."""

    harness = await repo.get_harness(harness_id, version)
    if harness is None:
        raise LookupError(f"Harness {harness_id} v{version} was not found.")
    return harness


async def _register_if_missing(repo: Any, service: Any, harness: Any) -> None:
    """Register a harness if the exact version is not already persisted."""

    existing = await repo.get_harness(harness.id, harness.version)
    if existing is None:
        await service.register_harness(harness)


def _resolve_harness_path(harness: str) -> Path:
    """Resolve a harness reference to a config file path."""

    candidate = Path(harness)
    if candidate.suffix in {".yaml", ".yml", ".json"}:
        return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
    return PROJECT_ROOT / "configs" / f"{harness}.yaml"


def _load_variant_definition(variant: str) -> Any:
    """Load a variant definition from disk."""

    from harness_foundry.schema.harness import VariantDefinition

    candidate = Path(variant)
    if candidate.suffix not in {".yaml", ".yml"}:
        candidate = PROJECT_ROOT / "configs" / "variants" / f"{variant}.yaml"
    elif not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    import yaml  # type: ignore[import-untyped]

    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    return VariantDefinition.model_validate(payload)


def _create_benchmark_runner() -> Any:
    """Create a benchmark runner with fake-model fallback when no API key is set."""

    from google.adk.agents.llm_agent import LlmAgent
    from google.genai import types

    from harness_foundry.evaluation.evaluators import Evaluator
    from harness_foundry.evaluation.runner import BenchmarkRunner
    from harness_foundry.processors.registry import registry as processor_registry
    from harness_foundry.runtime.adk_app import ADKApp
    from harness_foundry.runtime.compiler import HarnessCompiler
    from harness_foundry.runtime.runner import TaskRunner
    from harness_foundry.tracing.recorder import TraceRecorder

    compiler = HarnessCompiler(processor_registry)
    if not _has_live_model_access():

        def fake_compile(harness: Any) -> LlmAgent:
            async def before_model(*, callback_context, llm_request):  # type: ignore[no-untyped-def]
                from google.adk.models.llm_response import LlmResponse

                del llm_request
                state = getattr(callback_context, "state", {}) or {}
                fixture_state = state.get("harness:fixture_state", {})
                flattened = _flatten_fixture_values(fixture_state)
                response_text = "deterministic demo response"
                if flattened:
                    response_text = f"{response_text}: {' '.join(flattened)}"
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part(text=response_text)],
                    )
                )

            return LlmAgent(
                name=harness.agent.name,
                model=harness.model.model,
                instruction=harness.agent.instruction,
                before_model_callback=before_model,
            )

        compiler.compile = fake_compile  # type: ignore[method-assign]

    app_instance = ADKApp(compiler)
    tracer = TraceRecorder()
    evaluator = Evaluator()
    task_runner = TaskRunner(app=app_instance, tracer=tracer)
    return BenchmarkRunner(task_runner, evaluator, tracer)


def _flatten_fixture_values(value: Any) -> list[str]:
    """Flatten scalar fixture values to support fake-model responses."""

    if isinstance(value, dict):
        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_flatten_fixture_values(nested))
        return flattened
    if isinstance(value, list):
        flattened = []
        for nested in value:
            flattened.extend(_flatten_fixture_values(nested))
        return flattened
    if value is None:
        return []
    return [str(value)]


def _has_live_model_access() -> bool:
    """Return whether the CLI can attempt live ADK model execution."""

    settings = get_settings()
    configured_key = (
        settings.get("GOOGLE_API_KEY")
        if isinstance(settings, dict)
        else getattr(settings, "GOOGLE_API_KEY", None)
    )
    return bool(configured_key or GOOGLE_API_KEY)


def _parse_candidate_ref(candidate_id: str) -> tuple[str, str]:
    """Parse candidate refs in ``id@version`` or ``id:version`` form."""

    if "@" in candidate_id:
        harness_id, version = candidate_id.rsplit("@", 1)
        return harness_id, version
    if ":" in candidate_id:
        harness_id, version = candidate_id.rsplit(":", 1)
        return harness_id, version
    raise typer.BadParameter("candidate_id must be in the form <harness>@<version>.")


if __name__ == "__main__":
    app()
