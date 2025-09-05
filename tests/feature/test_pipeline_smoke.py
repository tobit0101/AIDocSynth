import asyncio
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from PySide6.QtCore import Qt

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.models.job import Job
from aidocsynth.ui.job_table_model import JobTableModel


# Helper functions and classes for mocking. Must be at top level to be pickleable.

def dummy_full_text(path):
    """Mocks the text extraction function."""
    return "dummy text"

class MockFileManager:
    """A pickleable mock for the FileManager."""
    def __init__(self, config):
        self.config = config  # Store config passed during instantiation

    def get_formatted_directory_structure(self):
        """Mocks directory structure retrieval."""
        return []

    def backup_original(self, src_path):
        """Mocks file backup."""
        pass

    def process_document(self, src_path, classification_data):
        """Mocks file processing and creates the target file for assertions."""
        # Use the instance's config, which is correctly set in the test's main process
        target_dir = self.config.work_dir / classification_data['target_directory']
        target_dir.mkdir(parents=True, exist_ok=True)
        new_path = target_dir / classification_data['target_filename']
        new_path.touch()
        return new_path

class MockMetadataService:
    """A pickleable mock for the MetadataService."""
    def get_file_metadata(self, path):
        """Mocks metadata retrieval."""
        return {}

@pytest.mark.qt
@pytest.mark.feature
def test_pipeline_and_table_update(mocker, workspace_dirs, mock_llm, qtbot):
    """A full smoke test for the main processing pipeline that also verifies table model updates."""
    # Mock components that run in a separate process to avoid PicklingError
    mocker.patch("aidocsynth.controllers.main_controller.full_text", new=dummy_full_text)
    mocker.patch("aidocsynth.controllers.main_controller.FileManager", new=MockFileManager)
    mocker.patch("aidocsynth.controllers.main_controller.MetadataService", new=MockMetadataService)

    # LLM provider is mocked via mock_llm fixture

    # Mock controller dependencies
    mock_view = MagicMock()
    mock_config_manager = MagicMock()
    mock_config_manager.data = settings.data  # Use the real settings object for the test

    # Instantiate controller and table model
    controller = MainController(config_manager=mock_config_manager, view=mock_view)
    tbl_model = JobTableModel()

    # Simulate binding signals
    controller.jobAdded.connect(tbl_model.add_job)
    controller.jobUpdated.connect(tbl_model.refresh)

    # Setup using shared workspace
    temp_dir = workspace_dirs
    dummy_file = temp_dir / "smoke_test.pdf"
    dummy_file.touch()

    # Action
    job = Job(path=str(dummy_file))

    # Simulate job being added and check table model
    controller.jobAdded.emit(job)
    assert tbl_model.rowCount() == 1, "Job should be added to the model immediately"

    # Run the pipeline
    asyncio.run(controller._pipeline(job))

    # Assert pipeline completion
    assert job.status == "done", f"Pipeline failed with status: {job.status}"
    sorted_path = settings.data.work_dir / "T" / "x.txt"
    assert sorted_path.exists(), f"Sorted file not found at {sorted_path}"

    # Assert table model update after pipeline completion
    assert tbl_model.rowCount() == 1, "Row count should remain 1 after update"
    idx_status = tbl_model.index(0, 2)  # Column 2 for Status
    assert tbl_model.data(idx_status, Qt.DisplayRole) == "done"

