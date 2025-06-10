import numpy as np, fitz, torch
from PIL import Image
from doctr.models import from_hub

_MODEL = None
_MODEL_ID = "Felix92/doctr-torch-parseq-multilingual-v1"

def _model():
    global _MODEL
    if _MODEL is None:
        m = from_hub(_MODEL_ID)
        _MODEL = m.to("cuda") if torch.cuda.is_available() else m
    return _MODEL

def _pdf_to_images(path: str, dpi: int = 300):
    doc = fitz.open(path)
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
        yield Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

async def ocr_text(path: str) -> str:
    if not path.lower().endswith(".pdf"):
        return ""
    imgs = [np.array(img) for img in _pdf_to_images(path)]
    result = _model()(imgs)
    return " ".join(w.value for p in result.pages
                              for b in p.blocks
                              for l in b.lines
                              for w in l.words)
