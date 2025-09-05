import asyncio
import os
import tempfile
import shutil
from pathlib import Path
import urllib.request
import json
import pytest
from unittest.mock import MagicMock

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.models.job import Job

@pytest.mark.e2e
def test_pipeline_with_ollama():
    """A real end-to-end test that uses an actual Ollama instance for classification.
    Skips automatically if Ollama is not reachable or the model is missing.
    """
    # Setup: Create temporary directories for output
    temp_dir = Path(tempfile.mkdtemp())
    settings.data.work_dir = temp_dir / "out"
    settings.data.backup_root = temp_dir / "out/backup"
    settings.data.unsorted_root = temp_dir / "out/unsorted"

    # Configure settings to use Ollama with the specified model
    settings.data.llm.provider = "ollama"
    # Use defaults; allow local overrides via environment if set
    settings.data.llm.ollama_model = os.environ.get("OLLAMA_MODEL", "mistral-nemo:12b-instruct-2407-q8_0")
    settings.data.llm.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    # Ensure directories exist
    settings.data.work_dir.mkdir(parents=True, exist_ok=True)
    settings.data.backup_root.mkdir(parents=True, exist_ok=True)
    settings.data.unsorted_root.mkdir(parents=True, exist_ok=True)

    # Probe Ollama endpoint, skip if not reachable
    try:
        with urllib.request.urlopen(f"{settings.data.llm.ollama_host}/api/tags", timeout=2) as resp:
            if resp.status != 200:
                pytest.skip("Ollama endpoint not reachable (non-200).")
            data = json.loads(resp.read().decode("utf-8"))
            # Optional: verify model presence; if absent, skip
            models = {m.get("name") for m in data.get("models", [])}
            if settings.data.llm.ollama_model not in models:
                pytest.skip(f"Model {settings.data.llm.ollama_model} not present on Ollama.")
    except Exception:
        pytest.skip("Ollama not running or unreachable.")

    # Use the real PDF from the shared tests/assets directory, copying it to the temp dir first
    # File is now under tests/e2e/, so go up two levels to project root
    project_root = Path(__file__).resolve().parents[2]
    original_pdf_path = project_root / "tests" / "assets" / "dummy.pdf"
    if not original_pdf_path.exists():
        pytest.skip("Test asset dummy.pdf not found.")
    pdf_path = temp_dir / original_pdf_path.name
    shutil.copy2(original_pdf_path, pdf_path)

    # Run the pipeline
    job = Job(path=str(pdf_path))
    mock_view = MagicMock()
    mock_cfg = MagicMock(); mock_cfg.data = settings.data
    controller = MainController(config_manager=mock_cfg, view=mock_view)
    try:
        asyncio.run(controller._pipeline(job))
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
