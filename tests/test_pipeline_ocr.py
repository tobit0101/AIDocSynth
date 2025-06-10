import json, tempfile, shutil
from pathlib import Path
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service  import settings

def test_pipeline_ocr(monkeypatch):
    temp = Path(tempfile.mkdtemp()); pdf = temp/"dummy.pdf"; pdf.write_bytes(b"%PDF-1.4")
    settings.data.work_dir = temp/"out"; settings.data.backup_root = temp/"out/backup"
    settings.data.unsorted_root = temp/"out/unsorted"

    # stubs
    monkeypatch.setattr("aidocsynth.services.text_pdf.extract_direct", lambda *_: "TXT")
    monkeypatch.setattr("aidocsynth.services.ocr_service.ocr_text", lambda *_: "OCR")
    monkeypatch.setattr(
        "aidocsynth.services.providers.dummy_provider.DummyProvider._run",
        lambda self, p: json.dumps({"targetPath":"T","fileName":"x.txt"})
    )

    MainController()._pipeline(type('Job', (object,), {'path': str(pdf)}))
    assert (settings.data.backup_root / pdf.name).exists()
    shutil.rmtree(temp)
