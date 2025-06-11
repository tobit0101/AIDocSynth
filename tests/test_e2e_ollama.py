import asyncio
import tempfile
import shutil
from pathlib import Path
import pytest

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.models.job import Job

# This test requires a running Ollama instance with the specified model.
# You can skip it by running: pytest -m "not e2e"
@pytest.mark.e2e
def test_pipeline_with_ollama():
    """An end-to-end test that uses a real Ollama instance for classification."""
    # Setup: Create temporary directories for output
    temp_dir = Path(tempfile.mkdtemp())
    settings.data.work_dir = temp_dir / "out"
    settings.data.backup_root = temp_dir / "out/backup"
    settings.data.unsorted_root = temp_dir / "out/unsorted"

    # Configure settings to use Ollama with the specified model
    settings.data.llm.provider = "ollama"
    settings.data.llm.ollama_model = "mistral-small3.1:24b-instruct-2503-q8_0"
    # Assuming Ollama runs on the default host
    settings.data.llm.ollama_host = "http://localhost:11434"

    # Use the real PDF for testing, copying it to the temp dir first
    test_assets_dir = Path(__file__).parent / "assets"
    original_pdf_path = test_assets_dir / "dummy.pdf"
    pdf_path = temp_dir / original_pdf_path.name
    shutil.copy2(original_pdf_path, pdf_path)

    # Run the pipeline
    job = Job(path=str(pdf_path))
    try:
        asyncio.run(MainController()._pipeline(job))
    except Exception as e:
        pytest.fail(f"Pipeline failed with an exception: {e}")

    # Assert: Check that the file was processed and not moved to 'unsorted'
    unsorted_path = settings.data.unsorted_root / pdf_path.name
    assert not unsorted_path.exists(), "File was moved to unsorted, indicating an error in the pipeline."

    # Check that some output was created in the work directory (excluding backup/unsorted)
    sorted_files = list(settings.data.work_dir.glob("**/*"))
    # Filter out directories and files in backup/unsorted folders
    sorted_files = [f for f in sorted_files if f.is_file() and 'backup' not in f.parts and 'unsorted' not in f.parts]
    assert len(sorted_files) > 0, "No sorted file was found in the output directory."

    # Teardown: Clean up the temporary directory
    shutil.rmtree(temp_dir)
