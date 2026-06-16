"""Report rendering for benchmark and comparison outputs."""

from __future__ import annotations

from harness_foundry.evaluation.scoring import BenchmarkReport, ComparisonReport


def render_benchmark_markdown(report: BenchmarkReport) -> str:
    """Render a benchmark report as Markdown."""

    lines = [
        f"# Benchmark Report: {report.harness_id}",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Split: `{report.split}`",
        f"- Model: `{report.model}`",
        f"- Total Score: `{report.total_score:.4f}`",
        f"- Pass Rate: `{report.pass_rate:.4f}`",
        "",
        "## Family Scores",
    ]
    for family, family_score in sorted(report.scores_by_family.items()):
        lines.append(
            f"- `{family}`: total=`{family_score.total_score:.4f}` "
            f"pass_rate=`{family_score.pass_rate:.4f}` tasks=`{family_score.task_count}`"
        )

    lines.extend(["", "## Task Scores"])
    for task_score in report.scores:
        lines.append(
            f"- `{task_score.task_id}`: total=`{task_score.total_score:.4f}` "
            f"passed=`{task_score.passed}` "
            f"failures={','.join(task_score.failure_codes) or 'none'}"
        )
    return "\n".join(lines)


def render_benchmark_json(report: BenchmarkReport) -> str:
    """Render a benchmark report as canonical JSON."""

    return report.model_dump_json(indent=2)


def render_comparison_markdown(report: ComparisonReport) -> str:
    """Render a comparison report as Markdown."""

    lines = [
        "# Comparison Report",
        "",
        f"- Baseline Run: `{report.baseline_run_id}`",
        f"- Candidate Run: `{report.candidate_run_id}`",
        f"- Global Delta: `{report.global_score.delta:.4f}`",
        f"- Pass Rate Delta: `{report.pass_rate.delta:.4f}`",
        "",
        "## Family Deltas",
    ]
    for family, delta in sorted(report.by_family.items()):
        lines.append(f"- `{family}`: delta=`{delta.delta:.4f}`")
    return "\n".join(lines)
