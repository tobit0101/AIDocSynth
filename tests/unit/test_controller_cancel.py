import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.models.job import Job


@pytest.mark.asyncio
async def test_pipeline_cancellation_before_start(workspace_dirs):
    base = workspace_dirs
    job_path = base / "to_cancel.pdf"
    job_path.write_bytes(b"data")

    mock_view = None
    mock_cfg = MagicMock(); mock_cfg.data = settings.data
    controller = MainController(config_manager=mock_cfg, view=mock_view)

    # Request cancellation before starting pipeline
    controller.request_cancellation()

    job = Job(path=str(job_path))
    with pytest.raises(asyncio.CancelledError):
        await controller._pipeline(job)

    assert job.status == "cancelled"


@pytest.mark.asyncio
async def test_update_job_progress_cancellation_raises(workspace_dirs):
    base = workspace_dirs
    p = base / "f.pdf"
    p.write_bytes(b"data")

    mock_view = None
    mock_cfg = MagicMock(); mock_cfg.data = settings.data
    controller = MainController(config_manager=mock_cfg, view=mock_view)

    job = Job(path=str(p))
    # Trigger cancellation before update call
    controller.request_cancellation()

    with pytest.raises(asyncio.CancelledError):
        await controller._update_job_progress(job, 20, "testing")

    assert job.status == "cancelled"


@pytest.mark.asyncio
async def test_pipeline_error_sets_job_status_error(monkeypatch, workspace_dirs):
    base = workspace_dirs
    p = base / "err.pdf"
    p.write_bytes(b"data")

    mock_view = None
    mock_cfg = MagicMock(); mock_cfg.data = settings.data
    controller = MainController(config_manager=mock_cfg, view=mock_view)

    # Avoid heavy OCR by short-circuiting text extraction
    async def fake_extract(self, job, src_path):
        return "TEXT"
    monkeypatch.setattr(MainController, "_extract_text_ocr", fake_extract)

    # Force classification stage to raise an exception directly
    async def boom(self, job, text_content, src_path):
        raise RuntimeError("classifier down")
    monkeypatch.setattr(MainController, "_classify_document", boom)

    job = Job(path=str(p))
    # Should not raise; pipeline catches and marks job as error
    await controller._pipeline(job)

    assert job.status == "error"
