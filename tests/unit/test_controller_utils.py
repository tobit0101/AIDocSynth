from unittest.mock import MagicMock
from pathlib import Path

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings
from aidocsynth.models.settings import AppSettings


class Label:
    def __init__(self):
        self.text = ""
    def setText(self, t: str):
        self.text = t


class MockView:
    def __init__(self):
        self.ocr_status_label = Label()
        self.actionStopProcessing = Action()
        self.workdir_label = ""

    def update_workdir_label(self, t: str):
        self.workdir_label = t

class Action:
    def __init__(self):
        self.enabled = False
    def setEnabled(self, v: bool):
        self.enabled = v


def test_open_working_directory_missing_shows_error(workspace_dirs):
    base = workspace_dirs
    # Point work_dir to a non-existent path
    missing = base / "does_not_exist"
    cfg = settings.data
    cfg.work_dir = missing

    mock_view = MockView()
    mock_cfg = MagicMock(); mock_cfg.data = cfg
    controller = MainController(config_manager=mock_cfg, view=mock_view)

    controller.open_working_directory()

    assert "Arbeitsverzeichnis nicht gefunden" in mock_view.ocr_status_label.text


def test_open_working_directory_openurl_failure(tmp_path, monkeypatch):
    # Use a temporary existing directory
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    mock_view = MockView()
    # Use isolated AppSettings to avoid mutating global settings
    cfg_data = AppSettings()
    cfg_data.work_dir = work_dir
    mock_cfg = MagicMock(); mock_cfg.data = cfg_data

    controller = MainController(config_manager=mock_cfg, view=mock_view)

    # Simulate openUrl failure and ensure os.path.exists returns True
    monkeypatch.setattr("aidocsynth.controllers.main_controller.os.path.exists", lambda p: True)
    monkeypatch.setattr("aidocsynth.controllers.main_controller.QDesktopServices.openUrl", lambda url: False)

    controller.open_working_directory()

    assert "Konnte Arbeitsverzeichnis nicht öffnen" in mock_view.ocr_status_label.text


def test_handle_drop_cancellation_skips_remaining(monkeypatch, tmp_path):
    # Prepare three dummy files
    f1 = tmp_path / "a.pdf"; f1.write_bytes(b"1")
    f2 = tmp_path / "b.pdf"; f2.write_bytes(b"2")
    f3 = tmp_path / "c.pdf"; f3.write_bytes(b"3")

    mock_view = MockView()
    cfg_data = AppSettings()
    mock_cfg = MagicMock(); mock_cfg.data = cfg_data
    controller = MainController(config_manager=mock_cfg, view=mock_view)

    # Do not actually start workers to keep test deterministic
    monkeypatch.setattr(controller.pool, "start", lambda w: None)

    first = {"done": False}

    def on_first_job(_job):
        # Cancel right after the first job is queued so remaining are skipped
        if not first["done"]:
            controller.request_cancellation()
            first["done"] = True

    controller.jobAdded.connect(on_first_job)

    controller.handle_drop([str(f1), str(f2), str(f3)])

    # After cancellation, only the first job should remain active
    assert controller.active_jobs == 1
    assert len(controller.workers) == 1
    # Stop action is disabled immediately upon cancellation to prevent repeated clicks
    assert mock_view.actionStopProcessing.enabled is False


def test_handle_settings_changed_updates_label_and_pool(tmp_path, monkeypatch):
    mock_view = MockView()
    cfg_data = AppSettings()
    cfg_data.work_dir = tmp_path / "initial"
    mock_cfg = MagicMock(); mock_cfg.data = cfg_data
    # Provide a mock settings_changed with connect attribute
    mock_cfg.settings_changed = MagicMock()

    controller = MainController(config_manager=mock_cfg, view=mock_view)

    # Capture thread pool size changes
    counts: list[int] = []
    monkeypatch.setattr(controller.pool, "setMaxThreadCount", lambda n: counts.append(n))

    # Serial mode should set count to 1
    cfg_data.processing_mode = "serial"
    cfg_data.max_parallel_processes = 5
    controller._handle_settings_changed()
    assert counts[-1] == 1

    # Parallel mode should use max_parallel_processes
    cfg_data.processing_mode = "parallel"
    cfg_data.max_parallel_processes = 7
    controller._handle_settings_changed()
    assert counts[-1] == 7

    # Changing work_dir should update the label
    new_dir = tmp_path / "new_work"
    cfg_data.work_dir = new_dir
    controller._handle_settings_changed()
    assert mock_view.workdir_label == str(new_dir)


def test_handle_drop_cancellation_immediate_skips_all(tmp_path, monkeypatch):
    # Prepare multiple dummy files
    f1 = tmp_path / "a.pdf"; f1.write_bytes(b"1")
    f2 = tmp_path / "b.pdf"; f2.write_bytes(b"2")

    mock_view = MockView()
    cfg_data = AppSettings()
    mock_cfg = MagicMock(); mock_cfg.data = cfg_data
    controller = MainController(config_manager=mock_cfg, view=mock_view)

    # Do not actually start workers
    monkeypatch.setattr(controller.pool, "start", lambda w: None)

    # Request cancellation before starting
    controller.request_cancellation()

    controller.handle_drop([str(f1), str(f2)])

    # handle_drop resets cancellation flag and enables processing; all files are queued
    assert controller.active_jobs == 2
    assert len(controller.workers) == 2
    assert mock_view.actionStopProcessing.enabled is True
