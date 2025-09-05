import json, shutil
from pathlib import Path
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service  import settings
from unittest.mock import MagicMock
import datetime
import os
import pytest

def _stub_full_text(_path: str) -> str:
    # Simple stub used by default ThreadPoolExecutor in tests
    return "STUB_OCR_TEXT"

@pytest.mark.feature
@pytest.mark.parametrize("asset_name", ["dummy.pdf", "sample.jpg"])
def test_pipeline_with_assets(workspace_dirs, mock_llm, monkeypatch, asset_name, assets_dir):
    # Patch the full_text symbol used inside MainController to keep CI fast
    monkeypatch.setattr("aidocsynth.controllers.main_controller.full_text", _stub_full_text)

    # Setup: copy the real asset into the temp workspace to exercise real I/O paths
    temp = workspace_dirs
    src = assets_dir / asset_name
    local_path = temp / src.name
    shutil.copy2(src, local_path)

    # Run the pipeline synchronously for the test
    import asyncio
    from aidocsynth.models.job import Job
    job = Job(path=str(local_path))
    mock_view = MagicMock()
    mock_cfg = MagicMock(); mock_cfg.data = settings.data
    controller = MainController(config_manager=mock_cfg, view=mock_view)
    # Use default thread executor in tests to avoid process pickling
    controller.process_pool = None
    asyncio.run(controller._pipeline(job))

    # Assert: Check if the file was backed up and sorted correctly.
    date_str = datetime.date.today().strftime("%Y%m%d")
    backup_path = settings.data.backup_root / date_str / local_path.name
    sorted_path = settings.data.work_dir / "T" / f"x{local_path.suffix.lower()}"

    assert backup_path.exists(), f"Backup file not found at {backup_path}"
    assert sorted_path.exists(), f"Sorted file not found at {sorted_path}"
    assert local_path.exists(), f"Source file was moved, but should have been copied."

    # No manual teardown needed; tmp_path handles cleanup

