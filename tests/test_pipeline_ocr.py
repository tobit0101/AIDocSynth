import json, tempfile, shutil
from pathlib import Path
from unittest.mock import AsyncMock
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service  import settings
import datetime

def test_pipeline_ocr(monkeypatch):
    # Setup: Create temporary directories for output
    temp = Path(tempfile.mkdtemp())
    settings.data.work_dir = temp / "out"
    settings.data.backup_root = temp / "out/backup"
    settings.data.unsorted_root = temp / "out/unsorted"

    # Use the real PDF for testing, but copy it to the temp dir first
    # to avoid modifying the original test asset.
    test_dir = Path(__file__).parent
    original_pdf_path = test_dir / "assets" / "dummy.pdf"
    pdf = temp / original_pdf_path.name
    shutil.copy2(original_pdf_path, pdf)

    # Stub the provider at the point of use to ensure it's always mocked
    mock_provider_instance = AsyncMock()
    mock_provider_instance.classify_document = AsyncMock(return_value={"targetPath": "T", "fileName": "x.txt"})
    monkeypatch.setattr(
        "aidocsynth.controllers.main_controller.get_provider",
        lambda cfg: mock_provider_instance
    )

    # Run the pipeline synchronously for the test
    import asyncio
    from aidocsynth.models.job import Job
    job = Job(path=str(pdf))
    asyncio.run(MainController()._pipeline(job))

    # Assert: Check if the file was backed up and sorted correctly.
    date_str = datetime.date.today().strftime("%Y%m%d")
    backup_path = settings.data.backup_root / date_str / pdf.name
    sorted_path = settings.data.work_dir / "T" / "x.txt"

    assert backup_path.exists(), f"Backup file not found at {backup_path}"
    assert sorted_path.exists(), f"Sorted file not found at {sorted_path}"
    assert pdf.exists(), f"Source file was moved, but should have been copied."

    # Teardown: Clean up the temporary directory
    shutil.rmtree(temp)

def test_pipeline_ocr_on_image(monkeypatch):
    # Setup: Create temporary directories for output
    temp = Path(tempfile.mkdtemp())
    settings.data.work_dir = temp / "out"
    settings.data.backup_root = temp / "out/backup"
    settings.data.unsorted_root = temp / "out/unsorted"

    # Use a real image for testing, copying it to the temp dir first.
    test_dir = Path(__file__).parent
    original_image_path = test_dir / "assets" / "sample.jpg"
    img_path = temp / original_image_path.name
    shutil.copy2(original_image_path, img_path)

    # Stub the provider at the point of use to ensure it's always mocked
    mock_provider_instance = AsyncMock()
    mock_provider_instance.classify_document = AsyncMock(return_value={"targetPath": "T", "fileName": "x.txt"})
    monkeypatch.setattr(
        "aidocsynth.controllers.main_controller.get_provider",
        lambda cfg: mock_provider_instance
    )

    # Run the pipeline synchronously for the test
    import asyncio
    from aidocsynth.models.job import Job
    job = Job(path=str(img_path))
    asyncio.run(MainController()._pipeline(job))

    # Assert: Check if the file was backed up and sorted correctly.
    date_str = datetime.date.today().strftime("%Y%m%d")
    backup_path = settings.data.backup_root / date_str / img_path.name
    sorted_path = settings.data.work_dir / "T" / "x.txt"

    assert backup_path.exists(), f"Backup file not found at {backup_path}"
    assert sorted_path.exists(), f"Sorted file not found at {sorted_path}"
    assert img_path.exists(), f"Source file was moved, but should have been copied."

    # Teardown: Clean up the temporary directory
    shutil.rmtree(temp)

