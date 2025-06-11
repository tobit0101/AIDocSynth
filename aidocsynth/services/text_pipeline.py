import fitz
from .ocr_service import ocr_text

def extract_direct(path: str) -> str:
    with fitz.open(path) as doc:
        return "\n".join(p.get_text() for p in doc)

def full_text(path: str) -> str:
    direct = extract_direct(path)
    ocr    = ocr_text(path)
    lines  = dict.fromkeys((direct + "\n" + ocr).splitlines())
    return "\n".join(lines)

def extract_text_stub(p): return f"Content of {p}"
