import tempfile
from pathlib import Path
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings

def test_pipeline_smoke(qtbot, mocker):
    """A full smoke test for the main processing pipeline using a dummy file."""
    # Mock the text extraction to avoid file format errors with dummy files
    mocker.patch("aidocsynth.controllers.main_controller.full_text", return_value="dummy text")

    # Setup
    controller = MainController()
    # Use a temporary directory managed by the test
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        # Configure settings to use this temporary directory
        settings.data.work_dir = temp_dir
        settings.data.backup_root = temp_dir / "backup"

        # Create a dummy file to process
        dummy_file = temp_dir / "smoke_test.pdf"
        dummy_file.touch()

        # Action & Assert
        # Use qtbot to wait for the pipeline to finish via the jobUpdated signal
        with qtbot.waitSignal(controller.jobUpdated, timeout=10000) as blocker:
            controller.handle_drop([str(dummy_file)])

        # Assert that the pipeline completed successfully
        assert blocker.signal_triggered, "The jobUpdated signal was not emitted."
        job = blocker.args[0] # The job is passed as the first argument of the signal
        assert job.status == "done", f"Pipeline failed with status: {job.status}"

        # Verify that the file was sorted correctly
        sorted_path = temp_dir / "T" / "x.txt"
        assert sorted_path.exists(), "Sorted file was not created."
