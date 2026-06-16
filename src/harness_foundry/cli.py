"""Typer CLI entry point for Adaptive Harness Foundry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

try:
    from harness_foundry.settings import DATABASE_URL, get_settings
except ImportError:
    from harness_foundry.settings import DATABASE_URL

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
) -> None:
    """Run benchmark tasks against a harness."""

    typer.echo(f"Running benchmark: {harness} v{version} split={split}")
    try:
        from harness_foundry.schema.harness import HarnessLoader

        loader_name = HarnessLoader.__name__
        typer.echo(
            "Not yet implemented — benchmark runner wiring is coming in Batch 1c "
            f"({loader_name} available)"
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


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

    typer.echo(f"Proposing evolution for {harness} v{version} run={run}")


@evolve_app.command("evaluate")
def evolve_evaluate(candidate_id: str) -> None:
    """Evaluate a candidate harness."""

    typer.echo(f"Evaluating candidate: {candidate_id}")


@app.command()
def promote(candidate_id: str) -> None:
    """Promote a candidate harness (requires passing promotion gate)."""

    typer.echo(f"Promoting candidate: {candidate_id}")


@app.command()
def rollback(
    harness: str = typer.Option(..., "--harness"),
    to_version: str = typer.Option(..., "--to-version"),
) -> None:
    """Rollback to a previous harness version."""

    typer.echo(f"Rolling back {harness} to v{to_version}")


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
def demo() -> None:
    """Run the complete proof-of-concept demo."""

    typer.echo("=" * 60)
    typer.echo("Adaptive Harness Foundry — Demo")
    typer.echo("=" * 60)
    try:
        from harness_foundry.schema.harness import HarnessLoader

        project_root = Path(__file__).resolve().parents[2]
        harness = HarnessLoader.load(project_root / "configs" / "baseline.yaml")
        settings = get_settings()

        typer.echo(f"\n✓ Loaded harness: {harness.id} v{harness.version}")
        typer.echo(f"  Model: {harness.model.model}")
        typer.echo(f"  Tools: {len(harness.tools.allow)} registered")
        typer.echo(f"  Processors: {sum(len(v) for v in harness.processors.values())} configured")
        if isinstance(settings, dict):
            database_url = settings.get("DATABASE_URL", DATABASE_URL)
        else:
            database_url = getattr(settings, "DATABASE_URL", DATABASE_URL)
        typer.echo(f"  Database: {database_url}")
        typer.echo("\nDemo complete. Full pipeline available in future phases.")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


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


if __name__ == "__main__":
    app()
