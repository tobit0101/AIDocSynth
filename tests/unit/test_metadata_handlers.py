from pathlib import Path

import fitz
from PIL import Image

from aidocsynth.services.metadata_service import MetadataService


def test_png_metadata_roundtrip(tmp_path: Path):
    # Create a simple PNG
    img_path = tmp_path / "sample.png"
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(img_path)

    service = MetadataService()
    meta = {
        "author": "Alice",
        "title": "Hello",
        "description": "Test PNG",
        "comment": "ignored for png get",
    }

    # Write and then read back
    ok = service.set_file_metadata(img_path, meta)
    assert ok is True

    read_back = service.get_file_metadata(img_path)
    # Only keys handled/read for PNG should be present
    assert read_back["author"] == "Alice"
    assert read_back["title"] == "Hello"
    assert read_back["description"] == "Test PNG"


def test_pdf_set_and_get_metadata(tmp_path: Path):
    # Create a 1-page PDF with some text
    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF")
    doc.save(pdf_path)
    doc.close()

    service = MetadataService()
    meta = {
        "title": "MyTitle",
        "author": "Bob",
        "subject": "Subject",
        "keywords": "k1, k2",
        "creator_tool": "AIDocSynth",
    }

    ok = service.set_file_metadata(pdf_path, meta)
    assert ok is True

    read_back = service.get_file_metadata(pdf_path)
    # Ensure at least some updated fields are present
    assert read_back.get("title") == "MyTitle"
    assert read_back.get("author") == "Bob"
    # subject/keywords may be omitted by backend if empty; ensure no crash and a dict is returned
    assert isinstance(read_back, dict)
