import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.models.job import Job

def test_pipeline_smoke(mocker):
    """A full smoke test for the main processing pipeline using a dummy file."""
    # Mock the text extraction to avoid file format errors with dummy files
    mocker.patch("aidocsynth.controllers.main_controller.full_text", return_value="dummy text")

    # Mock the provider
    mock_provider_instance = AsyncMock()
    mock_provider_instance.classify_document = AsyncMock(return_value={"targetPath": "smoke", "fileName": "test.txt"})
    mocker.patch("aidocsynth.controllers.main_controller.get_provider", lambda cfg: mock_provider_instance)

    # Setup
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        settings.data.work_dir = temp_dir
        settings.data.backup_root = temp_dir / "backup"
        settings.data.unsorted_root = temp_dir / "unsorted"

        dummy_file = temp_dir / "smoke_test.pdf"
        dummy_file.touch()

        # Action
        job = Job(path=str(dummy_file))
        asyncio.run(MainController()._pipeline(job))

        # Assert
        assert job.status == "done", f"Pipeline failed with status: {job.status}"
        sorted_path = settings.data.work_dir / "smoke" / "test.txt"
        assert sorted_path.exists(), f"Sorted file not found at {sorted_path}"


