from pathlib import Path

from aidocsynth.services.file_manager import FileManager
from aidocsynth.services.settings_service import settings


def _write(tmp: Path, name: str, content: bytes = b"x") -> Path:
    p = tmp / name
    p.write_bytes(content)
    return p


def test_process_document_absolute_target_path_outside_workspace_normalized(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "copy"
    fm = FileManager(cfg)

    src = _write(base, "abs_outside.pdf")

    # Compose an absolute path that is outside the workspace
    abs_outside = cfg.work_dir.resolve().parent / "OUTSIDE_TEST_DIR"
    classif = {"target_directory": str(abs_outside), "target_filename": "abs_outside.pdf"}

    newp = fm.process_document(src, classif)
    assert newp is not None and newp.exists()

    # New path must be inside the workspace
    work_dir_resolved = cfg.work_dir.resolve()
    new_parent_resolved = newp.parent.resolve()
    assert work_dir_resolved == new_parent_resolved or work_dir_resolved in new_parent_resolved.parents

    # Ensure we did not fall back to unsorted
    unsorted_candidate = cfg.unsorted_root / src.name
    assert not unsorted_candidate.exists()
