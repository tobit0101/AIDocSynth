import datetime
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Tuple

# Imports for metadata handling
import fitz  # PyMuPDF
from PIL import Image, PngImagePlugin
import piexif
from docx import Document
from docx.opc.exceptions import PackageNotFoundError as DocxPackageNotFoundError
from pptx import Presentation
from pptx.exc import PackageNotFoundError as PptxPackageNotFoundError
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException as OpenpyxlInvalidFileException

from aidocsynth.models.settings import AppSettings

logger = logging.getLogger(__name__)

COMMON_METADATA_KEYS = {
    "title": "title",
    "author": "author",
    "subject": "subject",
    "keywords": "keywords",
    "creator_tool": "creator_tool",
    "creation_date": "creation_date",
    "modification_date": "modification_date",
    "last_modified_by": "last_modified_by",
    "description": "description",
    "comment": "comment"
}

class FileManager:
    """Manages file operations like copying, sorting, and metadata handling."""

    def __init__(self, cfg: AppSettings):
        self.cfg = cfg
        self._metadata_handlers = self._register_metadata_handlers()

    def _register_metadata_handlers(self) -> Dict[str, Tuple[Callable, Callable]]:
        """Creates a registry mapping file extensions to metadata handlers."""
        return {
            '.pdf': (self._get_pdf_metadata, self._set_pdf_metadata),
            '.jpg': (self._get_image_metadata, self._set_image_metadata),
            '.jpeg': (self._get_image_metadata, self._set_image_metadata),
            '.png': (self._get_image_metadata, self._set_image_metadata),
            '.heic': (self._get_image_metadata, self._set_image_metadata),
            '.tiff': (self._get_image_metadata, self._set_image_metadata),
            '.tif': (self._get_image_metadata, self._set_image_metadata),
            '.docx': (self._get_docx_metadata, self._set_docx_metadata),
            '.pptx': (self._get_pptx_metadata, self._set_pptx_metadata),
            '.xlsx': (self._get_xlsx_metadata, self._set_xlsx_metadata),
        }

    def _copy_with_versioning(self, src: Path, dst_dir: Path, dst_name: str) -> Path:
        """Copies a file, handling versioning if the file already exists."""
        dst_dir.mkdir(parents=True, exist_ok=True)
        original_path = dst_dir / dst_name

        if not original_path.exists():
            shutil.copy2(src, original_path)
            return original_path

        stem, suffix = Path(dst_name).stem, Path(dst_name).suffix
        base_stem, start_idx = stem, 2

        match = re.match(r'(.+?)_v(\d+)$', stem)
        if match:
            base_stem = match.group(1)
            start_idx = int(match.group(2)) + 1

        for idx in range(start_idx, 1000):
            versioned_name = f"{base_stem}_v{idx:02d}{suffix}"
            versioned_path = dst_dir / versioned_name
            if not versioned_path.exists():
                shutil.copy2(src, versioned_path)
                logger.debug(f"Copied '{src}' to '{versioned_path}' with versioning.")
                return versioned_path

        raise FileExistsError(f"Could not save file {dst_name}. All versions up to 999 exist.")

    def _move_with_versioning(self, src: Path, dst_dir: Path, dst_name: str) -> Path:
        """Moves a file, handling versioning if the file already exists."""
        dst_dir.mkdir(parents=True, exist_ok=True)
        original_path = dst_dir / dst_name

        if not original_path.exists():
            shutil.move(str(src), original_path) # shutil.move needs string paths for cross-fs moves
            logger.debug(f"Moved '{src}' to '{original_path}'.")
            return original_path

        stem, suffix = Path(dst_name).stem, Path(dst_name).suffix
        base_stem, start_idx = stem, 2

        match = re.match(r'(.+?)_v(\d+)$', stem)
        if match:
            base_stem = match.group(1)
            start_idx = int(match.group(2)) + 1

        for idx in range(start_idx, 1000):
            versioned_name = f"{base_stem}_v{idx:02d}{suffix}"
            versioned_path = dst_dir / versioned_name
            if not versioned_path.exists():
                shutil.move(str(src), versioned_path)
                logger.debug(f"Moved '{src}' to '{versioned_path}' with versioning.")
                return versioned_path

        # If we reach here, it means we couldn't find a version slot. 
        # This case should be rare. We might want to raise an error or log a warning.
        # For now, let's log an error and not move the file to prevent data loss if src is deleted later.
        logger.error(f"Could not move file {dst_name} to {dst_dir}. All versions up to 999 exist.")
        raise FileExistsError(f"Could not move file {dst_name} to {dst_dir}. All versions up to 999 exist.")

    def backup_original(self, src: Path) -> Optional[Path]:
        """Creates a versioned copy of the original file in the backup directory if enabled."""
        if not self.cfg.create_backup:
            logger.info(f"Backup skipped for '{src.name}' as per settings.")
            return None

        if not self.cfg.backup_root:
            logger.error(f"Backup root directory is not configured. Cannot backup '{src.name}'.")
            return None
        
        backup_root_path = Path(self.cfg.backup_root)
        date_dir = backup_root_path / datetime.date.today().strftime("%Y%m%d")
        
        logger.info(f"Backing up (copy) '{src.name}' to '{date_dir}'.")
        # A backup is always a copy to preserve the original for processing.
        return self._copy_with_versioning(src, date_dir, src.name)



    def copy_unsorted(self, src: Path) -> Path:
        """Copies a file to the configured 'unsorted' directory."""
        return self._copy_with_versioning(src, self.cfg.unsorted_root, src.name)

    def get_directory_structure(self) -> list[tuple[str, int]]:
        """Gets the directory structure of the workspace as a list of (path, file_count)."""
        dir_list = []
        root_path = self.cfg.work_dir
        ignore_dirs = {self.cfg.unsorted_root.name, self.cfg.backup_root.name}

        for p in root_path.iterdir():
            if p.is_dir() and p.name not in ignore_dirs:
                self._walk_directory(p, root_path, dir_list)
        return dir_list

    def _walk_directory(self, current_dir: Path, root_path: Path, dir_list: list):
        """Recursively walks directories to build the structure list."""
        file_count = len([f for f in current_dir.iterdir() if f.is_file()])
        rel_path = current_dir.relative_to(root_path).as_posix()
        dir_list.append((rel_path, file_count))

        for p in current_dir.iterdir():
            if p.is_dir():
                self._walk_directory(p, root_path, dir_list)

    def get_formatted_directory_structure(self) -> str:
        """Gets the directory structure and formats it as a string for prompts."""
        dir_tuples = self.get_directory_structure()
        directory_structure = ""
        for path, count in dir_tuples:
            if count > 0:
                directory_structure += f"./{path} [Files: {count}]\n"
            else:
                directory_structure += f"./{path}\n"
        return directory_structure

    def process_document(self, src_path: Path, classification_data: dict) -> Optional[Path]:
        """Sorts a document by copying or moving it to the target directory based on settings."""
        src_name = src_path.name
        try:
            target_path_str = classification_data['target_path']
            file_name = classification_data['file_name']
            
            dst_dir = self.cfg.work_dir / target_path_str
            
            action_verb = "Moving" if self.cfg.sort_action == "move" else "Copying"
            logger.info(f"[{src_name}] {action_verb} file to '{target_path_str}' as '{file_name}'...")

            if self.cfg.sort_action == "move":
                if not src_path.exists():
                    logger.error(f"Source file '{src_path}' does not exist. Cannot move.")
                    return None
                new_path = self._move_with_versioning(src_path, dst_dir, file_name)
            else: # Default to "copy"
                new_path = self._copy_with_versioning(src_path, dst_dir, file_name)

            logger.info(f"[{src_name}] -> Success. Processing finished. New path: {new_path}")
            return new_path
            
        except (KeyError, TypeError) as e:
            logger.error(f"[{src_name}] -> Invalid classification data: {e}. Moving to unsorted.", exc_info=True)
            # If classification fails, we always copy to unsorted to avoid data loss.
            self.copy_unsorted(src_path)
            return None
        except Exception as e:
            logger.error(f"[{src_name}] -> Error during processing: {e}. Moving to unsorted.", exc_info=True)
            self.copy_unsorted(src_path)
            return None

    # --- Metadata Strategy --- #

    def get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Reads metadata from a file using a registered handler."""
        ext = file_path.suffix.lower()
        handler, _ = self._metadata_handlers.get(ext, (None, None))
        if not handler:
            logger.warning(f"Metadata extraction not supported for {ext} files.")
            return {}

        try:
            return handler(file_path)
        except (DocxPackageNotFoundError, PptxPackageNotFoundError, OpenpyxlInvalidFileException) as e:
            logger.error(f"Cannot open '{file_path.name}'. It might be corrupt or not a valid {ext} file. Error: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to read metadata for {file_path.name}: {e}", exc_info=True)
            return {}

    def set_file_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        """Writes metadata to a file using a registered handler."""
        ext = file_path.suffix.lower()
        _, handler = self._metadata_handlers.get(ext, (None, None))
        if not handler:
            logger.warning(f"Metadata setting not supported for {ext} files.")
            return False

        try:
            return handler(file_path, metadata)
        except (DocxPackageNotFoundError, PptxPackageNotFoundError, OpenpyxlInvalidFileException) as e:
            logger.error(f"Cannot open '{file_path.name}' to set metadata. Error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to set metadata for {file_path.name}: {e}", exc_info=True)
            return False

    # --- Individual Metadata Handlers --- #

    def _safe_decode(self, byte_string: Optional[bytes]) -> str:
        if byte_string is None: return ""
        try: return byte_string.decode('utf-8', errors='replace')
        except AttributeError: return str(byte_string)

    def _get_pdf_metadata(self, file_path: Path) -> Dict[str, Any]:
        with fitz.open(file_path) as doc:
            meta_doc = doc.metadata
            metadata = {
                COMMON_METADATA_KEYS["title"]: meta_doc.get("title", ""),
                COMMON_METADATA_KEYS["author"]: meta_doc.get("author", ""),
                COMMON_METADATA_KEYS["subject"]: meta_doc.get("subject", ""),
                COMMON_METADATA_KEYS["keywords"]: meta_doc.get("keywords", ""),
                COMMON_METADATA_KEYS["creator_tool"]: meta_doc.get("creator", ""),
                COMMON_METADATA_KEYS["creation_date"]: meta_doc.get("creationDate", ""),
                COMMON_METADATA_KEYS["modification_date"]: meta_doc.get("modDate", ""),
            }
            return {k: v for k, v in metadata.items() if v}

    def _set_pdf_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        with fitz.open(file_path) as doc:
            update_dict = {
                "title": metadata.get(COMMON_METADATA_KEYS["title"]),
                "author": metadata.get(COMMON_METADATA_KEYS["author"]),
                "subject": metadata.get(COMMON_METADATA_KEYS["subject"]),
                "keywords": metadata.get(COMMON_METADATA_KEYS["keywords"]),
                "creator": metadata.get(COMMON_METADATA_KEYS["creator_tool"]),
            }
            update_dict = {k: v for k, v in update_dict.items() if v is not None}
            if not update_dict:
                return True
            doc.set_metadata(update_dict)
            doc.save(str(file_path), incremental=False, encryption=fitz.PDF_ENCRYPT_KEEP)
        return True

    def _get_image_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = {}
        with Image.open(file_path) as img:
            img_info = img.info
            if file_path.suffix.lower() in (".jpg", ".jpeg", ".heic", ".tiff", ".tif") and "exif" in img_info:
                exif_dict = piexif.load(img_info["exif"])
                if exif_dict.get("0th"):
                    metadata[COMMON_METADATA_KEYS["author"]] = self._safe_decode(exif_dict["0th"].get(piexif.ImageIFD.Artist))
                    metadata[COMMON_METADATA_KEYS["description"]] = self._safe_decode(exif_dict["0th"].get(piexif.ImageIFD.ImageDescription))
                if exif_dict.get("Exif"):
                    metadata[COMMON_METADATA_KEYS["comment"]] = self._safe_decode(exif_dict["Exif"].get(piexif.ExifIFD.UserComment))
            elif file_path.suffix.lower() == ".png":
                for k, v in img_info.items():
                    if isinstance(v, str) and k.lower() in ["author", "title", "description"]:
                        metadata[COMMON_METADATA_KEYS.get(k.lower(), k)] = v
        return {k: v for k, v in metadata.items() if v}

    def _set_image_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        with Image.open(file_path) as img:
            img_info = img.info.copy()
            modified = False
            if file_path.suffix.lower() in (".jpg", ".jpeg", ".heic", ".tiff", ".tif"):
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
                    img.save(str(file_path), exif=exif_bytes)
            elif file_path.suffix.lower() == ".png":
                pnginfo = PngImagePlugin.PngInfo()
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

    def _get_office_metadata(self, doc) -> Dict[str, Any]:
        cp = doc.core_properties
        metadata = {
            COMMON_METADATA_KEYS["title"]: cp.title,
            COMMON_METADATA_KEYS["author"]: cp.author,
            COMMON_METADATA_KEYS["subject"]: cp.subject,
            COMMON_METADATA_KEYS["keywords"]: cp.keywords,
            COMMON_METADATA_KEYS["last_modified_by"]: cp.last_modified_by,
            COMMON_METADATA_KEYS["creation_date"]: cp.created.isoformat() if cp.created else None,
            COMMON_METADATA_KEYS["modification_date"]: cp.modified.isoformat() if cp.modified else None,
            COMMON_METADATA_KEYS["description"]: cp.comments,
        }
        return {k: v for k, v in metadata.items() if v is not None and v != ""}

    def _set_office_metadata(self, doc, metadata: Dict[str, Any], file_path: Path) -> bool:
        cp = doc.core_properties
        modified = False
        for key, prop_name in {
            COMMON_METADATA_KEYS["title"]: "title",
            COMMON_METADATA_KEYS["author"]: "author",
            COMMON_METADATA_KEYS["subject"]: "subject",
            COMMON_METADATA_KEYS["keywords"]: "keywords",
            COMMON_METADATA_KEYS["last_modified_by"]: "last_modified_by",
            COMMON_METADATA_KEYS["description"]: "comments",
        }.items():
            if key in metadata:
                setattr(cp, prop_name, metadata[key])
                modified = True
        if modified:
            doc.save(str(file_path))
        return True

    def _get_docx_metadata(self, file_path: Path) -> Dict[str, Any]:
        return self._get_office_metadata(Document(file_path))

    def _set_docx_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        doc = Document(file_path)
        return self._set_office_metadata(doc, metadata, file_path)

    def _get_pptx_metadata(self, file_path: Path) -> Dict[str, Any]:
        return self._get_office_metadata(Presentation(file_path))

    def _set_pptx_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        prs = Presentation(file_path)
        return self._set_office_metadata(prs, metadata, file_path)

    def _get_xlsx_metadata(self, file_path: Path) -> Dict[str, Any]:
        wb = openpyxl.load_workbook(file_path)
        props = wb.properties
        metadata = {
            COMMON_METADATA_KEYS["title"]: props.title,
            COMMON_METADATA_KEYS["author"]: props.creator,
            COMMON_METADATA_KEYS["subject"]: props.subject,
            COMMON_METADATA_KEYS["keywords"]: props.keywords,
            COMMON_METADATA_KEYS["last_modified_by"]: props.lastModifiedBy,
            COMMON_METADATA_KEYS["creation_date"]: props.created.isoformat() if props.created else None,
            COMMON_METADATA_KEYS["modification_date"]: props.modified.isoformat() if props.modified else None,
            COMMON_METADATA_KEYS["description"]: props.description,
        }
        return {k: v for k, v in metadata.items() if v is not None and v != ""}

    def _set_xlsx_metadata(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        wb = openpyxl.load_workbook(file_path)
        props = wb.properties
        modified = False

        mapping = {
            COMMON_METADATA_KEYS["title"]: "title",
            COMMON_METADATA_KEYS["author"]: "creator",
            COMMON_METADATA_KEYS["subject"]: "subject",
            COMMON_METADATA_KEYS["keywords"]: "keywords",
            COMMON_METADATA_KEYS["last_modified_by"]: "lastModifiedBy",
            COMMON_METADATA_KEYS["description"]: "description",
        }

        for key, prop_name in mapping.items():
            if key in metadata:
                setattr(props, prop_name, metadata[key])
                modified = True

        if modified:
            wb.save(str(file_path))
        return True
