import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from aidocsynth.services.ocr_service import initialize_ocr, ocr_text
from aidocsynth.services.settings_service import settings


@pytest.mark.e2e
def test_real_ocr_on_generated_image(tmp_path: Path):
    """
    Real OCR test using the actual doctr model (no mocks).
    - Generates a simple high-contrast image with text
    - Runs initialize_ocr() and ocr_text() for real inference
    - Skips if the model cannot be initialized in this environment
    """
    # Generate a simple image with black text on white background
    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((50, 80), "HELLO OCR TEST 123", fill="black")

    image_path = tmp_path / "ocr_test.png"
    img.save(image_path)

    # Ensure we don't unintentionally limit single-image processing
    settings.data.ocr_max_pages = max(1, settings.data.ocr_max_pages)

    # Try real model initialization; skip if not possible (e.g., no network, missing deps)
    try:
        initialize_ocr()
    except Exception as e:
        pytest.skip(f"doctr model could not be initialized: {e}")

    # Real OCR call
    out = ocr_text(str(image_path))

    # We don't assert exact text due to model variability; just ensure non-empty output
    assert isinstance(out, str) and out.strip() != "", "OCR output should be non-empty with real model"
