import torch
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
import logging
from threading import Lock

_MODEL = None
_MODEL_ID = "Felix92/doctr-torch-parseq-multilingual-v1"
_MODEL_LOCK = Lock()

logger = logging.getLogger(__name__)

def initialize_ocr(signals=None):
    """Loads the OCR predictor and replaces its recognition model with a custom one.
    Optionally emits progress updates via the provided signals object.
    """
    if signals:
        signals.progress_updated.emit("Initializing OCR engine...") # Initial status from service

    # Import doctr components here to delay their loading until this function is called
    from doctr.models import ocr_predictor, from_hub

    global _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            if signals:
                signals.progress_updated.emit(f"Lade Standard-Predictor (Modell: {_MODEL_ID})...")
            else:
                logger.info(f"Lade Standard-Predictor und ersetze reco_model mit: {_MODEL_ID}...")
            try:
                # 1. Load a standard pretrained predictor
                _MODEL = ocr_predictor(pretrained=True)
                
                # 2. Load the custom recognition model from the hub
                custom_reco_model = from_hub(_MODEL_ID)

                # 3. Replace the recognition model in the predictor
                _MODEL.reco_model = custom_reco_model

                if torch.cuda.is_available():
                    if signals:
                        signals.progress_updated.emit("CUDA verfügbar. Verschiebe Modell auf die GPU...")
                    else:
                        logger.info("CUDA verfügbar. Verschiebe Modell auf die GPU.")
                    _MODEL = _MODEL.to('cuda')
                if signals:
                    signals.progress_updated.emit("OCR-Predictor erfolgreich geladen und konfiguriert.")
                else:
                    logger.info("OCR-Predictor erfolgreich geladen und konfiguriert.")
                # Explicitly send ready signal from here for successful model init
                if signals:
                    signals.progress_updated.emit("OCR model ready.") 
            except Exception as e:
                logger.error(f"Kritisches Problem beim Laden des Modells: {e}", exc_info=True)
                if signals:
                    signals.progress_updated.emit(f"OCR Init Error: {e}") # Send specific error
                raise # Re-raise exception to trigger worker's error handling
        else:
            logger.info("OCR model already initialized. Skipping.")
            if signals: # Also signal ready if already initialized
                signals.progress_updated.emit("OCR model ready (already initialized).")
    return _MODEL

SUPPORTED_IMG_EXT = (".png", ".jpg", ".jpeg", ".tiff")

async def ocr_text(path: str, dpi: int = 300, signals=None) -> str:
    """Extracts text from a PDF or image file using the doctr OCR predictor.
    If 'signals' is provided, it's passed to initialize_ocr.
    """
    model = initialize_ocr(signals=signals)
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
