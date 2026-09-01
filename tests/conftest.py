"""Shared pytest fixtures for the engine tests."""
from __future__ import annotations

import pytest

from packing import Box, Config, load_boxes


@pytest.fixture
def catalog_boxes() -> list[Box]:
    return load_boxes()


@pytest.fixture
def default_config() -> Config:
    # Small time budget keeps randomized tests fast but deterministic.
    return Config(time_budget_ms=50)
