import importlib
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from aidocsynth.controllers.main_controller import MainController

def test_import():
    """Test that the main application module can be imported without errors."""
    importlib.import_module("aidocsynth.app")

def test_handle_drop_signal(monkeypatch, qtbot):
    """Test that handle_drop processes a file and emits the jobUpdated signal."""
    # Setup
    controller = MainController()
    monkeypatch.setattr(controller, "_pipeline", AsyncMock())

    with tempfile.TemporaryDirectory() as temp_dir:
        dummy_file = Path(temp_dir) / "test.pdf"
        dummy_file.touch()

        # Action & Assert
        with qtbot.waitSignal(controller.jobUpdated, timeout=5000) as blocker:
            controller.handle_drop([str(dummy_file)])

        assert blocker.signal_triggered, "Expected jobUpdated signal to be triggered."
        assert len(controller.workers) == 0, "Worker should be removed after completion."
