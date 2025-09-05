import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.services.classification_service import ClassificationService


class Action:
    def __init__(self):
        self.enabled = False
    def setEnabled(self, v: bool):
        self.enabled = v


class MinimalView:
    def __init__(self):
        self.actionStopProcessing = Action()


@pytest.mark.qt
def test_cancel_during_classification_no_crash(qtbot, monkeypatch, workspace_dirs):
    """
    Force a cancellation during the classification stage and verify that:
    - No crash occurs (Worker emits error/finished and controller cleans up).
    - Job status becomes 'cancelled' and never reaches 'done'.
    - UI state resets (stop action disabled), and 'Bereit' status is emitted.

    Strategy for stable timing:
    - Patch OCR extraction to be fast.
    - Patch ClassificationService.classify_document to poll the provided
      is_cancelled_callback and raise CancelledError once cancellation is requested.
    - Trigger request_cancellation() immediately after the controller emits
      a 'classifying' job update (observed via jobUpdated).
    """
    base: Path = workspace_dirs

    # Configure workspace and parallel settings (single job is sufficient)
    settings.data.work_dir = base / "out"
    settings.data.backup_root = settings.data.work_dir / "backup"
    settings.data.unsorted_root = settings.data.work_dir / "unsorted"
    settings.data.sort_action = "copy"
    settings.data.processing_mode = "parallel"
    settings.data.max_parallel_processes = 2

    (settings.data.work_dir / "T").mkdir(parents=True, exist_ok=True)

    # Create one input file
    f = base / "in.txt"; f.write_text("hello", encoding="utf-8")

    # Provide controller with current settings
    mock_cfg = MagicMock(); mock_cfg.data = settings.data

    # Fast OCR extraction (no heavy work)
    async def fast_extract(self, job, src_path: Path):
        await asyncio.sleep(0)  # yield to loop
        return "TEXT"
    monkeypatch.setattr(MainController, "_extract_text_ocr", fast_extract)

    # Classification stub that cancels once the test requests cancellation
    async def cancellable_classify(self, text_content: str, file_path: str, metadata, directory_structure, is_cancelled_callback=None):
        # Wait up to ~2s for cancellation to be requested, then raise
        for _ in range(100):
            if is_cancelled_callback and is_cancelled_callback():
                raise asyncio.CancelledError("cancelled by test")
            await asyncio.sleep(0.02)
        # If we reach here, cancellation wasn't issued in time; return a benign result
        # so the test can fail on assertions (it expects 'cancelled').
        src = Path(file_path)
        return {"target_directory": "T", "target_filename": f"{src.stem}_out{src.suffix}"}
    monkeypatch.setattr(ClassificationService, "classify_document", cancellable_classify)

    controller = MainController(config_manager=mock_cfg, view=MinimalView())

    statuses: list[str] = []
    msgs: list[str] = []
    controller.jobUpdated.connect(lambda j: statuses.append(j.status))
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    # Start processing
    controller.handle_drop([str(f)])

    # Wait until classification starts, then trigger cancellation
    qtbot.wait_until(lambda: any(s == "classifying" for s in statuses), timeout=5000)
    controller.request_cancellation()

    # Wait for pipeline to unwind and cleanup
    qtbot.wait_until(lambda: controller.active_jobs == 0 and len(controller.workers) == 0, timeout=5000)

    # Assertions: cancelled achieved, never done
    assert any(s == "cancelled" for s in statuses), f"Expected job to be cancelled, statuses: {statuses}"
    assert not any(s == "done" for s in statuses), f"Job unexpectedly completed, statuses: {statuses}"

    # UI reset: stop disabled; Status back to 'Bereit'
    assert controller.view.actionStopProcessing.enabled is False
    assert any("Bereit" in m for m in msgs)
