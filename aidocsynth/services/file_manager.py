import datetime
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from aidocsynth.models.settings import AppSettings

logger = logging.getLogger(__name__)

class FileManager:
    """Manages file operations like copying, sorting, and directory handling."""

    def __init__(self, cfg: AppSettings):
        self.cfg = cfg

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

    def _ensure_within_work_dir(self, path: Path) -> Path:
        """Resolve *path* and make sure it is located within the configured
        ``work_dir``.  This prevents accidental writes outside of the
        workspace.  Returns the resolved path on success, otherwise raises
        ``ValueError``.

        Parameters
        ----------
        path: Path
            Destination directory that should be created/used.
        """
        work_dir_resolved = self.cfg.work_dir.resolve()
        path_resolved = path.resolve()

        # ``work_dir`` must be a parent (or equal) of the destination.
        if work_dir_resolved == path_resolved or work_dir_resolved in path_resolved.parents:
            return path_resolved

        raise ValueError(
            f"Destination '{path_resolved}' is outside the workspace '{work_dir_resolved}'."
        )

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
                directory_structure += f"{path}/ [Files: {count}]\n"
            else:
                directory_structure += f"{path}/\n"
        return directory_structure

    def process_document(self, src_path: Path, classification_data: dict) -> Optional[Path]:
        """Sorts a document by copying or moving it to the target directory based on settings.

        The *classification_data* must contain a ``target_directory`` key that either
        holds a **relative** path inside the workspace or an **absolute** path
        that still points into the workspace. Any attempt to escape the
        workspace raises an exception and the document will be placed in the
        *unsorted* directory.
        """
        src_name = src_path.name
        try:
            target_directory_str = classification_data['target_directory']
            target_filename = classification_data['target_filename']

            # Ensure the target file name contains exactly the same extension as the
            # source (case-insensitive). If absent or different, enforce the
            # original suffix in lowercase to keep consistency.
            src_suffix_lower = src_path.suffix.lower()
            dst_suffix_lower = Path(target_filename).suffix.lower()
            if dst_suffix_lower == "" or dst_suffix_lower != src_suffix_lower:
                # Strip any wrong extension and append correct one
                target_filename = f"{Path(target_filename).stem}{src_suffix_lower}"
                logger.debug(
                    f"[{src_name}] Harmonised file extension. Using '{src_suffix_lower}' -> '{target_filename}'."
                )

            # Interpret absolute paths as-is (but enforce workspace boundaries).
            # For relative paths, also sanitize accidental leading slashes.
            raw_target = Path(target_directory_str)
            # Relative paths are interpreted relative to the workspace, absolute
            # paths are validated to still be inside the workspace.
            if raw_target.is_absolute():
                try:
                    dst_dir = self._ensure_within_work_dir(raw_target)
                except ValueError:
                    # If the model returned an absolute path that points outside the
                    # workspace, interpret it as an accidental absolute and treat it
                    # as a RELATIVE path within the workspace after stripping the
                    # leading separators. This keeps security (still inside
                    # workspace) while being robust to model outputs.
                    cleaned_target_directory_str = target_directory_str.lstrip('/\\')
                    logger.warning(
                        f"[{src_name}] -> Target directory '{target_directory_str}' is outside workspace. "
                        f"Interpreting as relative '{cleaned_target_directory_str}'."
                    )
                    dst_dir = self._ensure_within_work_dir(self.cfg.work_dir / Path(cleaned_target_directory_str))
            else:
                cleaned_target_directory_str = target_directory_str.lstrip('/\\')
                dst_dir = self._ensure_within_work_dir(self.cfg.work_dir / Path(cleaned_target_directory_str))
            
            action_verb = "Moving" if self.cfg.sort_action == "move" else "Copying"
            logger.info(f"[{src_name}] {action_verb} file to '{target_directory_str}' as '{target_filename}'...")

            if self.cfg.sort_action == "move":
                if not src_path.exists():
                    logger.error(f"Source file '{src_path}' does not exist. Cannot move.")
                    return None
                new_path = self._move_with_versioning(src_path, dst_dir, target_filename)
            else: # Default to "copy"
                new_path = self._copy_with_versioning(src_path, dst_dir, target_filename)

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
