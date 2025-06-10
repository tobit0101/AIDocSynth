import torch
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
from doctr.models import ocr_predictor, from_hub

_MODEL = None
_MODEL_ID = "Felix92/doctr-torch-parseq-multilingual-v1"

def initialize_ocr():
    """Loads the OCR predictor and replaces its recognition model with a custom one."""
    global _MODEL
    if _MODEL is None:
        print(f"Lade Standard-Predictor und ersetze reco_model mit: {_MODEL_ID}...")
        try:
            # 1. Load a standard pretrained predictor
            _MODEL = ocr_predictor(pretrained=True)
            
            # 2. Load the custom recognition model from the hub
            custom_reco_model = from_hub(_MODEL_ID)

            # 3. Replace the recognition model in the predictor
            _MODEL.reco_model = custom_reco_model

            if torch.cuda.is_available():
                print("CUDA verfügbar. Verschiebe Modell auf die GPU.")
                _MODEL = _MODEL.to('cuda')
            print("OCR-Predictor erfolgreich geladen und konfiguriert.")
        except Exception as e:
            print(f"Kritisches Problem beim Laden des Modells: {e}")
    return _MODEL

SUPPORTED_IMG_EXT = (".png", ".jpg", ".jpeg", ".tiff")

async def ocr_text(path: str, dpi: int = 300) -> str:
    """Extracts text from a PDF or image file using the doctr OCR predictor."""
    model = initialize_ocr()
    if not model:
        return ""

    file_path = str(path).lower()
    images = []
    try:
        if file_path.endswith(".pdf"):
            doc = fitz.open(path)
            images.extend(
                Image.frombytes("RGB", [p.width, p.height], p.samples)
                for page in doc
                for p in [page.get_pixmap(dpi=dpi)]
            )
            doc.close()
        elif file_path.endswith(SUPPORTED_IMG_EXT):
            images.append(Image.open(path).convert("RGB"))
        else:
            # Unsupported file type for OCR
            return ""

        if not images:
            return ""

        # Convert PIL images to numpy arrays
        numpy_images = [np.array(img) for img in images]

        # The predictor handles a list of numpy arrays and all pre/post-processing
        result = model(numpy_images)
        return result.render()

    except Exception as e:
        print(f"Fehler bei der Verarbeitung von '{path}': {e}")
        return ""
