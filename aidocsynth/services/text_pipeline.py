import fitz
from .ocr_service import ocr_text
from aidocsynth.services.settings_service import settings
import logging

# Stelle sicher, dass der Logger korrekt konfiguriert ist
logger = logging.getLogger(__name__)

# Füge einen Handler hinzu, falls noch keiner existiert und der Root-Logger auch keinen hat
if not logger.handlers and not logging.getLogger().handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

WORDS_PER_APPROXIMATED_PAGE = 300

def extract_direct(path: str) -> str:
    full_direct_text = ""
    with fitz.open(path) as doc:
        full_direct_text = "\n".join(p.get_text() for p in doc)
    
    words = full_direct_text.split()
    original_word_count = len(words)
    
    max_pages_setting = settings.data.ocr_max_pages
    word_limit_for_direct = max_pages_setting * WORDS_PER_APPROXIMATED_PAGE
    
    logger.info(f"Direct extraction: ocr_max_pages = {max_pages_setting}, approximating {WORDS_PER_APPROXIMATED_PAGE} words/page.")
    logger.info(f"Direct extraction: Calculated word limit = {word_limit_for_direct} words.")
    logger.info(f"Direct extraction: Original word count = {original_word_count} words.")

    if original_word_count > word_limit_for_direct:
        words = words[:word_limit_for_direct]
        logger.info(f"Direct extraction: Truncated from {original_word_count} to {word_limit_for_direct} words based on ocr_max_pages approximation.")
        return " ".join(words)
    
    return full_direct_text

MAX_FULL_TEXT_WORDS = 6000

def full_text(path: str) -> str:
    direct = extract_direct(path)
    ocr    = ocr_text(path)
    
    # Combine and deduplicate lines
    unique_lines = list(dict.fromkeys((direct + "\n" + ocr).splitlines()))
    combined_text_from_lines = "\n".join(unique_lines)
    
    words = combined_text_from_lines.split()
    original_word_count = len(words)
    
    logger.info(f"Word count direct extraction: {len(direct.split())}")
    logger.info(f"Word count OCR: {len(ocr.split())}")
    logger.info(f"Word count combined (before limit): {original_word_count}")

    if original_word_count > MAX_FULL_TEXT_WORDS:
        words = words[:MAX_FULL_TEXT_WORDS]
        logger.info(f"Truncated full_text from {original_word_count} to {MAX_FULL_TEXT_WORDS} words.")
    
    final_text = " ".join(words)
    
    # Log the first 50 words of the final text
    logger.info(f"First 50 words of final_text: {' '.join(words[:50])}")
    
    return final_text
