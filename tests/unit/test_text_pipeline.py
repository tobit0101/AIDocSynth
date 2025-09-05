from pathlib import Path
import pytest

from aidocsynth.services.text_pipeline import extract_direct, full_text
from aidocsynth.services.settings_service import settings


class FakePage:
    def __init__(self, text: str):
        self._text = text

    def get_text(self):
        return self._text


class FakeDoc:
    def __init__(self, text: str):
        self._page = FakePage(text)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter([self._page])


@pytest.mark.parametrize(
    "word_count, expected_count",
    [
        (500, 300),  # truncated to 300 words when over limit
        (100, 100),  # no truncation under limit
    ],
)
def test_extract_direct_truncation(monkeypatch, word_count, expected_count):
    # Limit to 1 page worth of words (300)
    settings.data.ocr_max_pages = 1
    words = [f"w{i}" for i in range(word_count)]

    monkeypatch.setattr(
        "fitz.open",
        lambda path: FakeDoc(" ".join(words)),
    )

    out = extract_direct("any.pdf")
    assert len(out.split()) == expected_count


@pytest.mark.parametrize(
    "direct,ocr,expected",
    [
        ("A\nB\nB\nC", "B\nC\nD", ["A", "B", "C", "D"]),
        ("hello", "world", ["hello", "world"]),
    ],
)
def test_full_text_deduplicates_lines_and_combines(monkeypatch, direct, ocr, expected):
    # Monkeypatch extract_direct and ocr_text to avoid OCR and PDF/OCR I/O
    monkeypatch.setattr(
        "aidocsynth.services.text_pipeline.extract_direct",
        lambda p: direct,
    )
    monkeypatch.setattr(
        "aidocsynth.services.text_pipeline.ocr_text",
        lambda p: ocr,
    )

    out = full_text("dummy.pdf")
    assert out.split() == expected


def test_full_text_truncates_to_max(monkeypatch):
    # Import lazily to allow monkeypatching and access MAX_FULL_TEXT_WORDS
    import aidocsynth.services.text_pipeline as tp

    # Create 7005 words total (over MAX_FULL_TEXT_WORDS=6000)
    direct_words = " ".join(["d"] * 4000)
    ocr_words = " ".join(["o"] * 3005)

    monkeypatch.setattr("aidocsynth.services.text_pipeline.extract_direct", lambda p: direct_words)
    monkeypatch.setattr("aidocsynth.services.text_pipeline.ocr_text", lambda p: ocr_words)

    out = tp.full_text("dummy.pdf")
    assert len(out.split()) == tp.MAX_FULL_TEXT_WORDS


def test_logger_handler_init_when_no_handlers(monkeypatch):
    # Import locally to avoid adding global imports
    import importlib
    import logging
    import sys

    # Remove module to force re-import
    sys.modules.pop("aidocsynth.services.text_pipeline", None)

    # Backup and remove all root handlers
    root_logger = logging.getLogger()
    old_handlers = list(root_logger.handlers)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    try:
        # Import module fresh so top-level logger init runs
        mod = importlib.import_module("aidocsynth.services.text_pipeline")
        # The module-level logger should now have a handler attached since root had none
        assert mod.logger.handlers, "Expected module logger to add a handler when none exist"
        # Also ensure level set at least to INFO as in module init
        assert mod.logger.level <= logging.INFO
    finally:
        # Restore root handlers to avoid impacting other tests
        for h in old_handlers:
            root_logger.addHandler(h)
        # Clean up imported module to avoid side effects for other tests
        sys.modules.pop("aidocsynth.services.text_pipeline", None)
        # Re-import normally to restore typical state for other tests
        importlib.import_module("aidocsynth.services.text_pipeline")
