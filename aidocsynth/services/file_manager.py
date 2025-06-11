import shutil, datetime, os, re
import logging
from pathlib import Path
from aidocsynth.models.settings import AppSettings

logger = logging.getLogger(__name__)

# Imports for metadata handling
try:
    import fitz  # PyMuPDF
except ImportError:
    logger.warning("PyMuPDF (fitz) not installed. PDF metadata functionality will be unavailable.")
    fitz = None

try:
    from PIL import Image, PngImagePlugin
except ImportError:
    logger.warning("Pillow not installed. Image metadata functionality will be unavailable.")
    Image = None
    PngImagePlugin = None

try:
    import piexif
except ImportError:
    logger.warning("piexif not installed. EXIF metadata functionality for JPEG/HEIC/TIFF will be unavailable.")
    piexif = None

try:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError as DocxPackageNotFoundError
except ImportError:
    logger.warning("python-docx not installed. DOCX metadata functionality will be unavailable.")
    Document = None
    DocxPackageNotFoundError = None

try:
    from pptx import Presentation
    from pptx.exc import PackageNotFoundError as PptxPackageNotFoundError
except ImportError:
    logger.warning("python-pptx not installed. PPTX metadata functionality will be unavailable.")
    Presentation = None
    PptxPackageNotFoundError = None

try:
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException as OpenpyxlInvalidFileException
except ImportError:
    logger.warning("openpyxl not installed. XLSX metadata functionality will be unavailable.")
    openpyxl = None
    OpenpyxlInvalidFileException = None

from typing import Dict, Any, Optional

def _copy_with_versioning(src: Path, dst_dir: Path, dst_name: str) -> Path:
    """
    Copies a file to a destination directory, handling versioning if the
    file already exists.
    If 'file.txt' exists, the next version will be 'file_v02.txt'.
    'file_v01.txt' is skipped unless specified as the destination name.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    original_path = dst_dir / dst_name

    # If the exact path doesn't exist, we can just use it.
    if not original_path.exists():
        shutil.copy2(src, original_path)
        return original_path

    # If the path *does* exist, we need to find a new versioned name.
    stem = Path(dst_name).stem
    suffix = Path(dst_name).suffix

    # Separate the base name from any existing version number (_vXX).
    base_stem = stem
    # If an un-versioned file exists, the first numbered version should be v02.
    start_idx = 2
    match = re.match(r'(.+?)_v(\d+)$', stem)
    if match:
        base_stem = match.group(1)
        # If a versioned file exists, start checking from the number *after* it.
        start_idx = int(match.group(2)) + 1

    # Find the next available version number.
    for idx in range(start_idx, 1000):
        versioned_name = f"{base_stem}_v{idx:02d}{suffix}"
        versioned_path = dst_dir / versioned_name
        if not versioned_path.exists():
            shutil.copy2(src, versioned_path)
            return versioned_path

    raise FileExistsError(
        f"Could not save file {dst_name}. All versions up to 999 exist."
    )

def backup_original(src: Path, cfg: AppSettings):
    d = cfg.backup_root / datetime.date.today().strftime("%Y%m%d")
    _copy_with_versioning(src, d, src.name)

def copy_sorted(src: Path, rel: str, name: str, cfg: AppSettings):
    dst_dir = cfg.work_dir / rel
    return _copy_with_versioning(src, dst_dir, name)

def copy_unsorted(src: Path, cfg: AppSettings):
    return _copy_with_versioning(src, cfg.unsorted_root, src.name)

def get_directory_structure(root_path):
    """Gets the directory structure as a list of tuples (path, file_count)."""
    dir_list = []
    # Note: topdown=True is the default, which allows modifying dirs
    for root, dirs, files in os.walk(root_path):
        # Prune 'unsorted' and 'backup' directories at the root level
        if os.path.samefile(root, root_path):
            if 'unsorted' in dirs:
                dirs.remove('unsorted')
            if 'backup' in dirs:
                dirs.remove('backup')

        rel_path = os.path.relpath(root, root_path)
        if rel_path != '.':
            dir_list.append((rel_path.replace("\\", "/"), len(files)))
    return dir_list

def sort_and_copy_document(src_path: Path, classification_data: dict, cfg: AppSettings):
    """
    Sorts a document based on classification data.

    Copies the file to the target directory on success, or to the unsorted
    directory on failure.

    Returns:
        str: "done" on success, "error" on failure.
    """
    src_name = src_path.name
    try:
        target_path = classification_data['targetPath']
        file_name = classification_data['fileName']
        logger.info(f"[{src_name}] Sorting file to '{target_path}' as '{file_name}'...")
        copy_sorted(src_path, target_path, file_name, cfg)
        logger.info(f"[{src_name}] -> Success. Sorting finished.")
        return "done"
    except (KeyError, TypeError) as e:
        logger.error(f"[{src_name}] -> Invalid classification data: {e}. Moving to unsorted.", exc_info=True)
        copy_unsorted(src_path, cfg)
        logger.info(f"[{src_name}] -> Finished with error.")
        return "error"
    except Exception as e:
        logger.error(f"[{src_name}] -> Error during sorting: {e}. Moving to unsorted.", exc_info=True)
        copy_unsorted(src_path, cfg)
        logger.info(f"[{src_name}] -> Finished with error.")
        return "error"

# --- Metadata Handling --- 

COMMON_METADATA_KEYS = {
    "title": "title",
    "author": "author",
    "subject": "subject",
    "keywords": "keywords",
    "creator_tool": "creator_tool", # e.g., software used to create the file
    "creation_date": "creation_date",
    "modification_date": "modification_date",
    "last_modified_by": "last_modified_by",
    "description": "description", # often same as subject
    "comment": "comment"
}

def _safe_decode(byte_string: Optional[bytes]) -> str:
    if byte_string is None:
        return ""
    try:
        return byte_string.decode('utf-8', errors='replace')
    except AttributeError:
        # If it's already a string
        return str(byte_string)

# PDF Metadata (using PyMuPDF)
def _get_pdf_metadata_fitz(doc: 'fitz.Document') -> Dict[str, Any]:
    metadata = {}
    if not fitz or not doc.metadata:
        return metadata
    
    meta_doc = doc.metadata
    logger.info(f"Raw PDF metadata for {doc.name}: {meta_doc}")
    metadata[COMMON_METADATA_KEYS["title"]] = meta_doc.get("title", "")
    metadata[COMMON_METADATA_KEYS["author"]] = meta_doc.get("author", "")
    metadata[COMMON_METADATA_KEYS["subject"]] = meta_doc.get("subject", "")
    metadata[COMMON_METADATA_KEYS["keywords"]] = meta_doc.get("keywords", "")
    metadata[COMMON_METADATA_KEYS["creator_tool"]] = meta_doc.get("creator", "") # Or producer
    # Get embedded dates
    creation_date_str = meta_doc.get("creationDate", "")
    mod_date_str = meta_doc.get("modDate", "")

    # If embedded creation date is empty, try filesystem ctime
    if not creation_date_str:
        try:
            ctime_timestamp = os.path.getctime(doc.name) # doc.name should be the full file path
            creation_date_str = datetime.datetime.fromtimestamp(ctime_timestamp).isoformat()
        except Exception as e:
            logger.warning(f"Could not get filesystem creation date for {doc.name}: {e}")

    # If embedded modification date is empty, try filesystem mtime
    if not mod_date_str:
        try:
            mtime_timestamp = os.path.getmtime(doc.name)
            mod_date_str = datetime.datetime.fromtimestamp(mtime_timestamp).isoformat()
        except Exception as e:
            logger.warning(f"Could not get filesystem modification date for {doc.name}: {e}")

    metadata[COMMON_METADATA_KEYS["creation_date"]] = creation_date_str
    metadata[COMMON_METADATA_KEYS["modification_date"]] = mod_date_str

    # Filter out other empty values, but always keep dates even if they ended up empty
    return {k: v for k, v in metadata.items() if v or k == COMMON_METADATA_KEYS["creation_date"] or k == COMMON_METADATA_KEYS["modification_date"]}

def _set_pdf_metadata_fitz(doc: 'fitz.Document', metadata: Dict[str, Any], file_path: Path) -> bool:
    if not fitz:
        return False
    
    current_meta = doc.metadata.copy()
    update_dict = {}
    if COMMON_METADATA_KEYS["title"] in metadata:
        update_dict["title"] = metadata[COMMON_METADATA_KEYS["title"]]
    if COMMON_METADATA_KEYS["author"] in metadata:
        update_dict["author"] = metadata[COMMON_METADATA_KEYS["author"]]
    if COMMON_METADATA_KEYS["subject"] in metadata:
        update_dict["subject"] = metadata[COMMON_METADATA_KEYS["subject"]]
    if COMMON_METADATA_KEYS["keywords"] in metadata:
        update_dict["keywords"] = metadata[COMMON_METADATA_KEYS["keywords"]]
    if COMMON_METADATA_KEYS["creator_tool"] in metadata:
        update_dict["creator"] = metadata[COMMON_METADATA_KEYS["creator_tool"]]
    if "creationDate" in metadata:
        update_dict["creationDate"] = metadata["creationDate"]
    if "modDate" in metadata:
        update_dict["modDate"] = metadata["modDate"]

    if not update_dict:
        logger.info(f"No metadata provided to set for {file_path.name}")
        return True

    current_meta.update(update_dict)
    
    try:
        doc.set_metadata(current_meta)
        doc.save(str(file_path), incremental=False, encryption=fitz.PDF_ENCRYPT_KEEP)
        return True
    except Exception as e:
        logger.error(f"Error setting PDF metadata for {file_path.name} using PyMuPDF: {e}", exc_info=True)
        return False

# Image Metadata (PIL/Pillow + piexif)
def _get_image_metadata_pil(file_path: Path) -> Dict[str, Any]:
    metadata = {}
    if not Image or not piexif:
        return metadata

    try:
        with Image.open(file_path) as img:
            img_info = img.info
            ext = file_path.suffix.lower()

            if ext in (".jpg", ".jpeg", ".heic", ".tiff", ".tif") and "exif" in img_info:
                exif_dict = piexif.load(img_info["exif"])
                if exif_dict.get("0th"):
                    metadata[COMMON_METADATA_KEYS["author"]] = _safe_decode(exif_dict["0th"].get(piexif.ImageIFD.Artist))
                    metadata[COMMON_METADATA_KEYS["modification_date"]] = _safe_decode(exif_dict["0th"].get(piexif.ImageIFD.DateTime))
                    metadata[COMMON_METADATA_KEYS["description"]] = _safe_decode(exif_dict["0th"].get(piexif.ImageIFD.ImageDescription))
                if exif_dict.get("Exif"):
                    metadata[COMMON_METADATA_KEYS["creation_date"]] = _safe_decode(exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal))
                    metadata[COMMON_METADATA_KEYS["comment"]] = _safe_decode(exif_dict["Exif"].get(piexif.ExifIFD.UserComment))
            
            elif ext == ".png":
                for k, v in img_info.items():
                    if isinstance(v, str):
                        if k.lower() == "author":
                             metadata[COMMON_METADATA_KEYS["author"]] = v
                        elif k.lower() == "title":
                             metadata[COMMON_METADATA_KEYS["title"]] = v
                        elif k.lower() == "description":
                             metadata[COMMON_METADATA_KEYS["description"]] = v
    except Exception as e:
        logger.error(f"Error reading image metadata for {file_path.name}: {e}", exc_info=True)
    
    return {k: v for k, v in metadata.items() if v}

def _set_image_metadata_pil(file_path: Path, metadata: Dict[str, Any]) -> bool:
    if not Image or not piexif or not PngImagePlugin:
        return False

    try:
        with Image.open(file_path) as img:
            img_info = img.info.copy()
            ext = file_path.suffix.lower()
            modified = False

            if ext in (".jpg", ".jpeg", ".heic", ".tiff", ".tif"):
                exif_dict = piexif.load(img_info.get("exif", b''))
                if COMMON_METADATA_KEYS["author"] in metadata:
                    exif_dict["0th"][piexif.ImageIFD.Artist] = metadata[COMMON_METADATA_KEYS["author"]].encode()
                    modified = True
                if COMMON_METADATA_KEYS["description"] in metadata:
                     exif_dict["0th"][piexif.ImageIFD.ImageDescription] = metadata[COMMON_METADATA_KEYS["description"]].encode()
                     modified = True
                if COMMON_METADATA_KEYS["comment"] in metadata:
                    exif_dict["Exif"][piexif.ExifIFD.UserComment] = metadata[COMMON_METADATA_KEYS["comment"]].encode()
                    modified = True
                
                if modified:
                    exif_bytes = piexif.dump(exif_dict)
                    save_kwargs = {}
                    if "icc_profile" in img_info: save_kwargs["icc_profile"] = img_info["icc_profile"]
                    if ext in (".jpg", ".jpeg"):
                        for key in ["quality", "jfif_unit", "jfif_density", "dpi", "progression", "adobe", "adobe_transform"]:
                            if key in img_info: save_kwargs[key] = img_info[key]
                        if "quality" not in save_kwargs: save_kwargs["quality"] = 95
                    
                    img.save(str(file_path), exif=exif_bytes, **save_kwargs)
                return True

            elif ext == ".png":
                pnginfo = PngImagePlugin.PngInfo()
                for key, value in img_info.items():
                    if key.lower() not in ["author", "title", "description"] and isinstance(value, str):
                        pnginfo.add_text(key, value)

                if COMMON_METADATA_KEYS["author"] in metadata:
                    pnginfo.add_text("Author", metadata[COMMON_METADATA_KEYS["author"]])
                    modified = True
                if COMMON_METADATA_KEYS["title"] in metadata:
                    pnginfo.add_text("Title", metadata[COMMON_METADATA_KEYS["title"]])
                    modified = True
                if COMMON_METADATA_KEYS["description"] in metadata:
                    pnginfo.add_text("Description", metadata[COMMON_METADATA_KEYS["description"]])
                    modified = True
                
                if modified:
                    img.save(str(file_path), pnginfo=pnginfo)
                return True
            
            logger.warning(f"Metadata setting for {ext} not fully supported or no changes made.")
            return True

    except Exception as e:
        logger.error(f"Error setting image metadata for {file_path.name}: {e}", exc_info=True)
        return False

# DOCX Metadata (python-docx)
def _get_docx_metadata(doc: 'docx.document.Document') -> Dict[str, Any]:
    metadata = {}
    if not Document or not doc.core_properties:
        return metadata
    cp = doc.core_properties
    metadata[COMMON_METADATA_KEYS["title"]] = cp.title
    metadata[COMMON_METADATA_KEYS["author"]] = cp.author
    metadata[COMMON_METADATA_KEYS["subject"]] = cp.subject
    metadata[COMMON_METADATA_KEYS["keywords"]] = cp.keywords
    metadata[COMMON_METADATA_KEYS["last_modified_by"]] = cp.last_modified_by
    metadata[COMMON_METADATA_KEYS["creation_date"]] = cp.created.isoformat() if cp.created else None
    metadata[COMMON_METADATA_KEYS["modification_date"]] = cp.modified.isoformat() if cp.modified else None
    metadata[COMMON_METADATA_KEYS["description"]] = cp.comments
    return {k: v for k, v in metadata.items() if v is not None and v != ""}

def _set_docx_metadata(doc: 'docx.document.Document', metadata: Dict[str, Any], file_path: Path) -> bool:
    if not Document:
        return False
    cp = doc.core_properties
    modified = False
    if COMMON_METADATA_KEYS["title"] in metadata: cp.title = metadata[COMMON_METADATA_KEYS["title"]]; modified = True
    if COMMON_METADATA_KEYS["author"] in metadata: cp.author = metadata[COMMON_METADATA_KEYS["author"]]; modified = True
    if COMMON_METADATA_KEYS["subject"] in metadata: cp.subject = metadata[COMMON_METADATA_KEYS["subject"]]; modified = True
    if COMMON_METADATA_KEYS["keywords"] in metadata: cp.keywords = metadata[COMMON_METADATA_KEYS["keywords"]]; modified = True
    if COMMON_METADATA_KEYS["last_modified_by"] in metadata: cp.last_modified_by = metadata[COMMON_METADATA_KEYS["last_modified_by"]]; modified = True
    if COMMON_METADATA_KEYS["description"] in metadata: cp.comments = metadata[COMMON_METADATA_KEYS["description"]]; modified = True
    if modified:
        try:
            doc.save(str(file_path))
            return True
        except Exception as e:
            logger.error(f"Error saving DOCX metadata for {file_path.name}: {e}", exc_info=True)
            return False
    return True

# PPTX Metadata (python-pptx)
def _get_pptx_metadata(prs: 'pptx.presentation.Presentation') -> Dict[str, Any]:
    metadata = {}
    if not Presentation or not prs.core_properties:
        return metadata
    cp = prs.core_properties
    metadata[COMMON_METADATA_KEYS["title"]] = cp.title
    metadata[COMMON_METADATA_KEYS["author"]] = cp.author
    metadata[COMMON_METADATA_KEYS["subject"]] = cp.subject
    metadata[COMMON_METADATA_KEYS["keywords"]] = cp.keywords
    metadata[COMMON_METADATA_KEYS["last_modified_by"]] = cp.last_modified_by
    metadata[COMMON_METADATA_KEYS["creation_date"]] = cp.created.isoformat() if cp.created else None
    metadata[COMMON_METADATA_KEYS["modification_date"]] = cp.modified.isoformat() if cp.modified else None
    return {k: v for k, v in metadata.items() if v is not None and v != ""}

def _set_pptx_metadata(prs: 'pptx.presentation.Presentation', metadata: Dict[str, Any], file_path: Path) -> bool:
    if not Presentation:
        return False
    cp = prs.core_properties
    modified = False
    if COMMON_METADATA_KEYS["title"] in metadata: cp.title = metadata[COMMON_METADATA_KEYS["title"]]; modified = True
    if COMMON_METADATA_KEYS["author"] in metadata: cp.author = metadata[COMMON_METADATA_KEYS["author"]]; modified = True
    if COMMON_METADATA_KEYS["subject"] in metadata: cp.subject = metadata[COMMON_METADATA_KEYS["subject"]]; modified = True
    if COMMON_METADATA_KEYS["keywords"] in metadata: cp.keywords = metadata[COMMON_METADATA_KEYS["keywords"]]; modified = True
    if COMMON_METADATA_KEYS["last_modified_by"] in metadata: cp.last_modified_by = metadata[COMMON_METADATA_KEYS["last_modified_by"]]; modified = True
    if modified:
        try:
            prs.save(str(file_path))
            return True
        except Exception as e:
            logger.error(f"Error saving PPTX metadata for {file_path.name}: {e}", exc_info=True)
            return False
    return True

# XLSX Metadata (openpyxl)
def _get_xlsx_metadata(wb: 'openpyxl.workbook.workbook.Workbook') -> Dict[str, Any]:
    metadata = {}
    if not openpyxl or not wb.properties:
        return metadata
    props = wb.properties
    metadata[COMMON_METADATA_KEYS["title"]] = props.title
    metadata[COMMON_METADATA_KEYS["author"]] = props.creator
    metadata[COMMON_METADATA_KEYS["subject"]] = props.subject
    metadata[COMMON_METADATA_KEYS["keywords"]] = props.keywords
    metadata[COMMON_METADATA_KEYS["last_modified_by"]] = props.lastModifiedBy
    metadata[COMMON_METADATA_KEYS["creation_date"]] = props.created.isoformat() if hasattr(props, 'created') and props.created else None
    metadata[COMMON_METADATA_KEYS["modification_date"]] = props.modified.isoformat() if hasattr(props, 'modified') and props.modified else None
    metadata[COMMON_METADATA_KEYS["description"]] = props.description
    return {k: v for k, v in metadata.items() if v is not None and v != ""}

def _set_xlsx_metadata(wb: 'openpyxl.workbook.workbook.Workbook', metadata: Dict[str, Any], file_path: Path) -> bool:
    if not openpyxl:
        return False
    props = wb.properties
    modified = False
    if COMMON_METADATA_KEYS["title"] in metadata: props.title = metadata[COMMON_METADATA_KEYS["title"]]; modified = True
    if COMMON_METADATA_KEYS["author"] in metadata: props.creator = metadata[COMMON_METADATA_KEYS["author"]]; modified = True
    if COMMON_METADATA_KEYS["subject"] in metadata: props.subject = metadata[COMMON_METADATA_KEYS["subject"]]; modified = True
    if COMMON_METADATA_KEYS["keywords"] in metadata: props.keywords = metadata[COMMON_METADATA_KEYS["keywords"]]; modified = True
    if COMMON_METADATA_KEYS["last_modified_by"] in metadata: props.lastModifiedBy = metadata[COMMON_METADATA_KEYS["last_modified_by"]]; modified = True
    if COMMON_METADATA_KEYS["description"] in metadata: props.description = metadata[COMMON_METADATA_KEYS["description"]]; modified = True
    if modified:
        try:
            wb.save(str(file_path))
            return True
        except Exception as e:
            logger.error(f"Error saving XLSX metadata for {file_path.name}: {e}", exc_info=True)
            return False
    return True

# Main public functions
def get_file_metadata(file_path: Path) -> Dict[str, Any]:
    """Reads metadata from PDF, Office, and image files."""
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"File not found or is not a file: {file_path}")
        return {}

    ext = file_path.suffix.lower()
    metadata_dict = {}

    try:
        if ext == ".pdf":
            if not fitz: return {}
            with fitz.open(file_path) as doc:
                metadata_dict = _get_pdf_metadata_fitz(doc)
        elif ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic"):
            if not Image or not piexif: return {}
            metadata_dict = _get_image_metadata_pil(file_path)
        elif ext == ".docx":
            if not Document: return {}
            try:
                doc = Document(file_path)
                metadata_dict = _get_docx_metadata(doc)
            except DocxPackageNotFoundError:
                logger.warning(f"Could not read {file_path.name}, possibly not a valid DOCX file or encrypted.")
        elif ext == ".pptx":
            if not Presentation: return {}
            try:
                prs = Presentation(file_path)
                metadata_dict = _get_pptx_metadata(prs)
            except PptxPackageNotFoundError:
                 logger.warning(f"Could not read {file_path.name}, possibly not a valid PPTX file or encrypted.")
        elif ext == ".xlsx":
            if not openpyxl: return {}
            try:
                wb = openpyxl.load_workbook(file_path)
                metadata_dict = _get_xlsx_metadata(wb)
            except OpenpyxlInvalidFileException:
                logger.warning(f"Could not read {file_path.name}, possibly not a valid XLSX file or encrypted.")
        else:
            logger.info(f"Metadata extraction not supported for file type: {ext}")
    except Exception as e:
        logger.error(f"Failed to read metadata for {file_path.name}: {e}", exc_info=True)
    
    return metadata_dict

def set_file_metadata(file_path: Path, metadata: Dict[str, Any]) -> bool:
    """Writes metadata to PDF, Office, and image files. Overwrites the original file."""
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"File not found or is not a file: {file_path}")
        return False

    ext = file_path.suffix.lower()
    success = False

    try:
        if ext == ".pdf":
            if not fitz: return False
            with fitz.open(file_path) as doc: 
                success = _set_pdf_metadata_fitz(doc, metadata, file_path)
        elif ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic"):
            if not Image or not piexif or not PngImagePlugin: return False
            success = _set_image_metadata_pil(file_path, metadata)
        elif ext == ".docx":
            if not Document: return False
            try:
                doc = Document(file_path)
                success = _set_docx_metadata(doc, metadata, file_path)
            except DocxPackageNotFoundError:
                logger.warning(f"Could not write metadata to {file_path.name}, possibly not a valid DOCX file or encrypted.")
        elif ext == ".pptx":
            if not Presentation: return False
            try:
                prs = Presentation(file_path)
                success = _set_pptx_metadata(prs, metadata, file_path)
            except PptxPackageNotFoundError:
                 logger.warning(f"Could not write metadata to {file_path.name}, possibly not a valid PPTX file or encrypted.")
        elif ext == ".xlsx":
            if not openpyxl: return False
            try:
                wb = openpyxl.load_workbook(file_path)
                success = _set_xlsx_metadata(wb, metadata, file_path)
            except OpenpyxlInvalidFileException:
                logger.warning(f"Could not write metadata to {file_path.name}, possibly not a valid XLSX file or encrypted.")
        else:
            logger.info(f"Metadata setting not supported for file type: {ext}")
    except Exception as e:
        logger.error(f"Failed to set metadata for {file_path.name}: {e}", exc_info=True)

    return success
