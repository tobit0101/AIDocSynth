import os
from pathlib import Path

from aidocsynth.services.file_manager import FileManager
from aidocsynth.services.settings_service import settings


def _write(tmp: Path, name: str, content: bytes = b"data") -> Path:
    p = tmp / name
    p.write_bytes(content)
    return p


def test_process_copy_versioning(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "copy"
    fm = FileManager(cfg)

    src1 = _write(base, "src1.pdf")
    classif = {"target_directory": "T", "target_filename": "target.pdf"}

    new1 = fm.process_document(src1, classif)
    assert new1 is not None and new1.exists()
    assert new1.name == "target.pdf"
    # Source should remain after copy
    assert src1.exists()

    src2 = _write(base, "src2.pdf")
    new2 = fm.process_document(src2, classif)
    assert new2 is not None and new2.exists()
    assert new2.name == "target_v02.pdf"
    assert src2.exists()


def test_process_move_versioning(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "move"
    fm = FileManager(cfg)

    src1 = _write(base, "m1.pdf")
    src2 = _write(base, "m2.pdf")
    classif = {"target_directory": "T", "target_filename": "same.pdf"}

    new1 = fm.process_document(src1, classif)
    new2 = fm.process_document(src2, classif)

    assert new1 is not None and new1.exists()
    assert new2 is not None and new2.exists()
    assert new1.name == "same.pdf"
    assert new2.name == "same_v02.pdf"
    # Source files should be moved
    assert not src1.exists()
    assert not src2.exists()


def test_workspace_boundary_moves_to_unsorted(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "copy"
    fm = FileManager(cfg)

    src = _write(base, "in.pdf")
    classif = {"target_directory": "../../outside", "target_filename": "x.pdf"}

    res = fm.process_document(src, classif)
    assert res is None
    # File copied to unsorted
    uns = cfg.unsorted_root / src.name
    assert uns.exists()


def test_unsorted_on_invalid_classification(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    fm = FileManager(cfg)

    src = _write(base, "bad.pdf")
    # Missing required keys
    res = fm.process_document(src, {})
    assert res is None
    assert (cfg.unsorted_root / src.name).exists()


def test_extension_is_preserved_lowercased(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "copy"
    fm = FileManager(cfg)

    src = _write(base, "input.PDF")
    # Provider suggests different extension; FileManager must enforce original lowercase ext
    classif = {"target_directory": "T", "target_filename": "out.TXT"}
    new_path = fm.process_document(src, classif)

    assert new_path is not None
    assert new_path.suffix == ".pdf"
    assert new_path.name == "out.pdf"


def test_copy_versioning_respects_existing_suffix_increment(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "copy"
    fm = FileManager(cfg)

    # First copy uses a filename with an existing version suffix
    src1 = _write(base, "v1.pdf")
    classif = {"target_directory": "T", "target_filename": "same_v03.pdf"}
    new1 = fm.process_document(src1, classif)
    assert new1 is not None and new1.exists()
    assert new1.name == "same_v03.pdf"

    # Second copy should increment from v03 -> v04 (regex branch)
    src2 = _write(base, "v2.pdf")
    new2 = fm.process_document(src2, classif)
    assert new2 is not None and new2.exists()
    assert new2.name == "same_v04.pdf"
    # Source should remain after copy
    assert src2.exists()


def test_backup_original_disabled_and_no_root(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    fm = FileManager(cfg)

    src = _write(base, "b.pdf")

    # If backups are disabled, nothing should be done
    cfg.create_backup = False
    res = fm.backup_original(src)
    assert res is None

    # If backup_root is missing, backup should be skipped gracefully
    cfg.create_backup = True
    cfg.backup_root = None
    res = fm.backup_original(src)
    assert res is None


def test_get_directory_structure_and_formatted(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    fm = FileManager(cfg)

    # Create directories and files inside the workspace
    dA = cfg.work_dir / "A"
    dB = dA / "B"
    dC = cfg.work_dir / "C"
    dA.mkdir(parents=True, exist_ok=True)
    dB.mkdir(parents=True, exist_ok=True)
    dC.mkdir(parents=True, exist_ok=True)

    (dA / "f1.txt").write_text("x")
    (dB / "f2.txt").write_text("y")

    # Unsorted and backup are present but should be ignored by listing
    cfg.unsorted_root.mkdir(exist_ok=True)
    cfg.backup_root.mkdir(exist_ok=True)

    structure = fm.get_directory_structure()
    # Convert to dict for easy lookup
    struct_dict = {path: count for path, count in structure}
    assert struct_dict.get("A") == 1
    assert struct_dict.get("A/B") == 1
    assert struct_dict.get("C") == 0

    formatted = fm.get_formatted_directory_structure()
    # Lines with files include a count, empty dirs do not
    assert "A/ [Files: 1]" in formatted
    assert "A/B/ [Files: 1]" in formatted
    # Directory with 0 files should be present without count suffix
    assert any(line.strip() == "C/" for line in formatted.splitlines())


def test_process_document_absolute_target_path_inside_workspace(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "copy"
    fm = FileManager(cfg)

    src = _write(base, "abs.pdf")
    abs_target = (cfg.work_dir / "AA").resolve()
    classif = {"target_directory": str(abs_target), "target_filename": "abs.pdf"}

    newp = fm.process_document(src, classif)
    assert newp is not None and newp.exists()
    assert newp.parent == abs_target


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


def test_process_move_missing_source_returns_none(workspace_dirs):
    base = workspace_dirs
    cfg = settings.data
    cfg.sort_action = "move"
    fm = FileManager(cfg)

    src = cfg.work_dir / "does-not-exist.pdf"
    classif = {"target_directory": "T", "target_filename": "foo.pdf"}

    res = fm.process_document(src, classif)
    assert res is None
