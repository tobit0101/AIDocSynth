import shutil, datetime, os, re
import logging
from pathlib import Path
from aidocsynth.models.settings import AppSettings

logger = logging.getLogger(__name__)

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
