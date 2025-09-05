import shutil
from pathlib import Path
import pytest

from aidocsynth.services.ocr_service import ocr_text
from aidocsynth.services.settings_service import settings


class _FakeOCRResult:
    def render(self) -> str:
        return "FAKE_OCR_TEXT"


class _FakeOCRModel:
    def __call__(self, numpy_images):
        # Simulate processing; we don't care about images' content here
        return _FakeOCRResult()


@pytest.mark.feature
@pytest.mark.parametrize("asset_name", ["dummy.pdf", "sample.jpg"])
def test_ocr_text_with_assets_uses_conversion_pipeline(monkeypatch, workspace_dirs, asset_name, assets_dir):
    # Replace heavy model initialization with a tiny fake model
    monkeypatch.setattr(
        "aidocsynth.services.ocr_service.initialize_ocr",
        lambda signals=None: _FakeOCRModel(),
    )

    # Keep it quick and deterministic
    settings.data.ocr_max_pages = 1

    # Copy real asset into temp workspace to exercise PyMuPDF/PIL conversion paths
    temp = workspace_dirs
    src = assets_dir / asset_name
    local = temp / src.name
    shutil.copy2(src, local)

    out = ocr_text(str(local))

    # We assert on the fake model's output, ensuring our pipeline reached it
    assert out == "FAKE_OCR_TEXT"
