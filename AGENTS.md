# AGENTS.md — Guidelines for Adaptive Harness Foundry

This document captures the conventions and guidelines that all contributors
and AI coding agents should follow when working on **Adaptive Harness Foundry**.

**Tech Stack:** Python 3.12, Google ADK v2.2+, Pydantic v2, SQLAlchemy 2, FastAPI, Typer, pytest, Ruff, mypy

---

## 1. Code Organisation

- `src/harness_foundry/` — all application code under the `harness_foundry` package
- Module boundaries follow the architectural planes: catalog/, schema/, runtime/, processors/, tools/, tracing/, evaluation/, evolution/, api/, ui/
- Each module has its own `__init__.py` exporting public API
- Imports: stdlib → third-party → first-party (alphabetical within groups)
- Single responsibility per module — no "utils.py" catch-all

## 2. Error Handling

- Use Pydantic `ValidationError` for schema violations
- Use custom `HarnessError` hierarchy for domain errors (`CompilationError`, `ValidationError`, `PromotionError`)
- Async functions use `try/except` with structured error logging
- Never swallow exceptions silently — at minimum, log with structlog

## 3. Python Conventions

- Python 3.12+ — use `str | None` over `Optional[str]`, PEP 695 generics where appropriate
- Pydantic v2 `model_config` pattern: `model_config = ConfigDict(...)`
- All public functions have type annotations
- Prefer `async def` for ADK callbacks and tools (ADK requires async for some contexts)
- Use `ClassVar` for true class-level constants that shouldn't become model fields

## 4. Testing

- Location: `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/adversarial/`, `tests/e2e/`
- Framework: pytest + pytest-asyncio
- Test what the code should do, not how it does it
- ADK integration tests use the fake-model pattern (callback-based deterministic responses)
- Run: `uv run pytest tests/ -v` (use PYTHONPATH bypass for CI without dev deps)
- Benchmark determinism: identical configs + identical fixtures must produce identical scores

## 5. Documentation

- Docstrings for all public APIs (Google style)
- Architecture decisions in `docs/adr/` (numbered, dated, status)
- Schema documentation auto-generated from Pydantic models
- README must stay current with implemented features

## 6. Performance

- Profile before optimizing
- SQLite with WAL mode for concurrent reads
- Trace events use bulk inserts
- Benchmark runner processes tasks serially (simplicity over throughput for POC)

## 7. Dependencies

- Managed via `uv` with `pyproject.toml`
- `uv.lock` committed to repo
- No `pip install` outside of `pyproject.toml` dependencies
- Dependency additions require justification

## 8. Formatting and Linting

- Ruff for formatting and linting: `ruff format src/ tests/ && ruff check src/ tests/`
- Mypy for type checking: `mypy src/`
- Pre-commit hooks enforce formatting

## 9. CI / CD

- `make lint` — ruff format check + ruff check
- `make typecheck` — mypy
- `make test` — full test suite (requires GOOGLE_API_KEY for live tests)
- `make test-ci` — deterministic tests only (no API key required)

## 10. References

- `PYTHON_DEVELOPMENT.md` — detailed Python patterns and conventions
- `docs/architecture.md` — system architecture
- `docs/harness-schema.md` — harness configuration schema
- [Google ADK docs](https://adk.dev/)
