from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from aidocsynth.services.settings_service import settings


@pytest.fixture
def workspace_dirs(tmp_path: Path):
    """Provide an isolated temporary workspace and backup/unsorted folders.

    - Sets settings.data to point into tmp_path/out
    - Ensures directories exist
    - Forces create_backup=True to have deterministic expectations
    - Restores original settings after the test
    """
    snapshot = settings.data.model_copy(deep=True)

    base = tmp_path
    s = settings.data
    s.work_dir = base / "out"
    s.backup_root = s.work_dir / "backup"
    s.unsorted_root = s.work_dir / "unsorted"
    s.create_backup = True

    s.work_dir.mkdir(parents=True, exist_ok=True)
    s.backup_root.mkdir(parents=True, exist_ok=True)
    s.unsorted_root.mkdir(parents=True, exist_ok=True)

    try:
        yield base
    finally:
        # Restore snapshot to avoid leaking state across tests
        settings.data = snapshot


@pytest.fixture
def mock_llm(monkeypatch):
    """Mock the LLM provider returned by get_provider() with sane defaults."""
    provider = AsyncMock()
    provider.classify_document = AsyncMock(
        return_value={"target_directory": "T", "target_filename": "x.txt"}
    )
    monkeypatch.setattr(
        "aidocsynth.controllers.main_controller.get_provider",
        lambda cfg: provider,
    )
    return provider


@pytest.fixture
def assets_dir() -> Path:
    """Return the shared tests/assets directory regardless of test subfolder.

    Keeping this in the root tests/conftest.py ensures all tests can reference
    the same assets location even after reorganizing tests into subfolders.
    """
    return Path(__file__).parent / "assets"
