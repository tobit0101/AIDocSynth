from .text_pdf   import extract_direct
from .ocr_service import ocr_text

def full_text(path: str) -> str:
    direct = extract_direct(path)
    ocr    = ocr_text(path)
    lines  = dict.fromkeys((direct + "\n" + ocr).splitlines())
    return "\n".join(lines)

def extract_text_stub(p): return f"Content of {p}"
