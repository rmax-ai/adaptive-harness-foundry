"""Smoke tests for the Typer CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from harness_foundry.cli import app

runner = CliRunner()


def test_catalog_list() -> None:
    result = runner.invoke(app, ["catalog", "list"])
    assert result.exit_code == 0


def test_validate_baseline() -> None:
    result = runner.invoke(app, ["validate", "configs/baseline.yaml"])
    assert result.exit_code == 0


def test_demo() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "Demo complete" in result.stdout


def test_demo_help() -> None:
    result = runner.invoke(app, ["demo", "--help"])
    assert result.exit_code == 0
    assert "Run the complete proof-of-concept demo." in result.stdout
