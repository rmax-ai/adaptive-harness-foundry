"""Test configuration for Adaptive Harness Foundry.

Provides fixtures for deterministic testing without live API calls.
"""
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def data_dir(project_root):
    """Return the data directory."""
    return project_root / "data"


@pytest.fixture(scope="session")
def configs_dir(project_root):
    """Return the configs directory."""
    return project_root / "configs"
