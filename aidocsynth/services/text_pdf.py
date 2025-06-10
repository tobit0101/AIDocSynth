import fitz
def extract_direct(path: str) -> str:
    with fitz.open(path) as doc:
        return "\n".join(p.get_text() for p in doc)
