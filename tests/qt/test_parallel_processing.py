import asyncio
import time
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
def test_parallel_two_jobs_classification_runs_concurrently(qtbot, monkeypatch, workspace_dirs):
    """
    Real-near parallel test:
    - Uses real MainController pipeline and QThreadPool with parallel mode (2 threads)
    - Uses real filesystem (backup/process) and async pipeline structure
    - Stubs only heavy OCR (extract) and LLM classification logic (to avoid network)

    We assert concurrency by recording the start times of the classification stage for
    two jobs and ensuring they overlap (i.e., start within a small threshold).
    """
    base: Path = workspace_dirs

    # Configure real-near settings
    settings.data.work_dir = base / "out"
    settings.data.backup_root = settings.data.work_dir / "backup"
    settings.data.unsorted_root = settings.data.work_dir / "unsorted"
    settings.data.sort_action = "copy"
    settings.data.processing_mode = "parallel"
    settings.data.max_parallel_processes = 2

    (settings.data.work_dir / "T").mkdir(parents=True, exist_ok=True)

    # Create two small input files (text is enough since we stub extraction)
    f1 = base / "in1.txt"; f1.write_text("hello 1", encoding="utf-8")
    f2 = base / "in2.txt"; f2.write_text("hello 2", encoding="utf-8")

    # Make a config_manager mock that provides current settings
    mock_cfg = MagicMock(); mock_cfg.data = settings.data

    # Stub only the text extraction to avoid heavy OCR/CPU
    async def fast_extract(self, job, src_path: Path):
        await asyncio.sleep(0)  # yield to loop
        return "TEXT"
    monkeypatch.setattr(MainController, "_extract_text_ocr", fast_extract)

    # Instrument the classification stage to simulate workload and record start times
    start_times: list[float] = []
    async def fake_classify(self, text_content: str, file_path: str, metadata, directory_structure, is_cancelled_callback=None):
        start_times.append(time.perf_counter())
        await asyncio.sleep(0.3)  # simulate real LLM latency
        src = Path(file_path)
        # Ensure distinct filenames to avoid collisions
        return {
            "target_directory": "T",
            "target_filename": f"{src.stem}_out{src.suffix}",
        }
    monkeypatch.setattr(ClassificationService, "classify_document", fake_classify)

    # Build controller with a minimal view (enables stop button)
    controller = MainController(config_manager=mock_cfg, view=MinimalView())

    # Drop two files – expect two workers to start concurrently under parallel mode
    t0 = time.perf_counter()
    controller.handle_drop([str(f1), str(f2)])

    # Wait for both workers to finish (workers set empty and active_jobs == 0)
    qtbot.wait_until(lambda: controller.active_jobs == 0 and len(controller.workers) == 0, timeout=5000)
    elapsed = time.perf_counter() - t0

    # Concurrency evidence: both classification stages should start near each other
    assert len(start_times) == 2, "Both classification stages should have started"
    start_times.sort()
    assert (start_times[1] - start_times[0]) < 0.5, "Classification stages did not overlap sufficiently (no parallelism?)"

    # Sanity: Overall time should be closer to single-task time than sum of two
    # Allow generous headroom for CI variance
    assert elapsed < 1.5, f"Parallel run took too long ({elapsed:.2f}s), expected < 1.5s"

    # Outputs should exist in target directory
    out_dir = settings.data.work_dir / "T"
    assert (out_dir / "in1_out.txt").exists()
    assert (out_dir / "in2_out.txt").exists()
