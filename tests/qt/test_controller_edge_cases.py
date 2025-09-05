import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from aidocsynth.controllers.main_controller import MainController
from aidocsynth.models.settings import AppSettings


class Action:
    def __init__(self):
        self.enabled = False
    def setEnabled(self, v: bool):
        self.enabled = v


class MinimalView:
    def __init__(self):
        self.actionStopProcessing = Action()


class Label:
    def __init__(self):
        self.text = ""
    def setText(self, t: str):
        self.text = t


class ViewWithLabel(MinimalView):
    def __init__(self):
        super().__init__()
        self.ocr_status_label = Label()


def make_cfg(work_dir: Path | str | None = None):
    cfg = AppSettings()
    if work_dir is not None:
        cfg.work_dir = Path(work_dir)
    mock_cfg = MagicMock(); mock_cfg.data = cfg
    return mock_cfg


def test_open_working_directory_missing_dir_no_view(tmp_path, monkeypatch):
    # Point to a non-existing directory
    missing = tmp_path / "does_not_exist"
    controller = MainController(config_manager=make_cfg(missing), view=None)

    # Should not raise even with missing view/label
    controller.open_working_directory()


def test_open_working_directory_open_fails_without_label(tmp_path, monkeypatch):
    d = tmp_path / "exists"; d.mkdir()
    controller = MainController(config_manager=make_cfg(d), view=MinimalView())

    # Force openUrl to fail
    monkeypatch.setattr("aidocsynth.controllers.main_controller.QDesktopServices.openUrl", lambda url: False)

    # Should log error but not crash and not try to set a non-existent label
    controller.open_working_directory()


def test_settings_connect_guard_when_no_signal(tmp_path):
    # Build a config_manager WITHOUT a settings_changed signal
    cfg = AppSettings(); cfg.work_dir = tmp_path
    config_manager = SimpleNamespace(data=cfg)

    # Should not crash in __init__ when trying to connect
    controller = MainController(config_manager=config_manager, view=None)
    # And calling handler should work
    controller._handle_settings_changed()


def test_handle_drop_enables_stop_action_when_view_present(tmp_path, monkeypatch):
    controller = MainController(config_manager=make_cfg(tmp_path), view=ViewWithLabel())
    # Avoid starting real workers
    monkeypatch.setattr(controller.pool, "start", lambda w: None)

    f = tmp_path / "a.pdf"; f.write_text("x")
    controller.handle_drop([str(f)])
    assert controller.view.actionStopProcessing.enabled is True


def test_handle_drop_cancellation_skips_remaining_and_resets_ui(tmp_path, monkeypatch, qtbot):
    controller = MainController(config_manager=make_cfg(tmp_path), view=ViewWithLabel())

    # Make pool.start toggle cancellation after first start
    started = {"count": 0}
    def fake_start(worker):
        started["count"] += 1
        if started["count"] == 1:
            # Trigger cancellation before the second iteration
            controller.request_cancellation()
    monkeypatch.setattr(controller.pool, "start", fake_start)

    # Use duplicate paths so list.index(p) returns 0 for second iteration
    f = tmp_path / "d.pdf"; f.write_text("x")
    controller.handle_drop([str(f), str(f)])

    # After cancellation branch, active_jobs should be reset to 0 and button disabled
    assert controller.active_jobs == 0
    assert controller.view.actionStopProcessing.enabled is False


def test_handle_drop_index_value_error_path(tmp_path, monkeypatch):
    controller = MainController(config_manager=make_cfg(tmp_path), view=ViewWithLabel())

    # Start will set cancellation after first item is queued
    started = {"count": 0}
    def fake_start(worker):
        started["count"] += 1
        if started["count"] == 1:
            controller._cancellation_requested = True
    monkeypatch.setattr(controller.pool, "start", fake_start)

    class OddList:
        def __init__(self, items):
            self._items = items
        def __len__(self):
            return len(self._items)
        def __iter__(self):
            for x in self._items:
                yield x
        def index(self, value):
            # Pretend the second value is not found
            if value == self._items[1]:
                raise ValueError("not found")
            return 0

    f1 = str(tmp_path / "a.pdf"); (tmp_path / "a.pdf").write_text("x")
    f2 = str(tmp_path / "b.pdf"); (tmp_path / "b.pdf").write_text("y")

    # Should not raise despite ValueError during index lookup
    controller.handle_drop(OddList([f1, f2]))


@pytest.mark.asyncio
async def test_pipeline_cancelled_without_extra_update_when_status_already_cancelled(monkeypatch, qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)

    # Capture emissions to ensure no extra emit happens in exception branch
    emissions = []
    controller.jobUpdated.connect(lambda j: emissions.append(j.status))

    # Monkeypatch update_job_progress to set status and then raise without emitting
    async def fake_update(self, job, progress, status, log_message_prefix="", result=None):
        job.status = "cancelled"
        raise asyncio.CancelledError("stop")
    monkeypatch.setattr(MainController, "_update_job_progress", fake_update)

    job = type("J", (), {"path": "/tmp/f.pdf", "status": ""})()

    with pytest.raises(asyncio.CancelledError):
        await controller._pipeline(job)

    # Status should remain 'cancelled' and no further emit attempted in exception branch
    assert job.status == "cancelled"
    assert emissions == []


def test_update_job_on_error_cancelled_no_emit(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    from aidocsynth.models.job import Job
    job = Job(path="/tmp/x.pdf")
    job.status = "cancelled"

    statuses: list[str] = []
    controller.jobUpdated.connect(lambda j: statuses.append(j.status))

    # Already cancelled -> branch should exit without emitting
    controller.update_job_on_error(job, asyncio.CancelledError())
    assert statuses == []


@pytest.mark.asyncio
async def test_pipeline_cancelled_sets_status_when_not_pre_set(monkeypatch):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)

    # Make extract step raise CancelledError without setting job.status first
    async def raise_cancel(*args, **kwargs):
        raise asyncio.CancelledError("stop mid");

    # Avoid doing real work in backup
    async def no_backup(*args, **kwargs):
        return None

    monkeypatch.setattr(MainController, "_backup_file", no_backup)
    monkeypatch.setattr(MainController, "_extract_text_ocr", raise_cancel)

    from aidocsynth.models.job import Job
    job = Job(path="/tmp/a.pdf")

    statuses: list[str] = []
    controller.jobUpdated.connect(lambda j: statuses.append(j.status))

    with pytest.raises(asyncio.CancelledError):
        await controller._pipeline(job)

    # Since status was not set before, the exception handler should set it and emit
    assert "cancelled" in statuses


def test_handle_drop_cancellation_without_action_stop(tmp_path, monkeypatch):
    # view=None ensures branch without actionStopProcessing
    controller = MainController(config_manager=make_cfg(tmp_path), view=None)

    # Simulate cancellation triggered after first worker start
    started = {"count": 0}
    def fake_start(worker):
        started["count"] += 1
        if started["count"] == 1:
            controller.request_cancellation()
    monkeypatch.setattr(controller.pool, "start", fake_start)

    f = tmp_path / "c.pdf"; f.write_text("x")
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    # Duplicate paths so skipped_count logic uses index 0 on second iteration
    controller.handle_drop([str(f), str(f)])

    assert controller.active_jobs == 0
    assert any("Bereit" in m for m in msgs)


def test_handle_drop_empty_noop(monkeypatch, qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=ViewWithLabel())
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    # Passing an empty list should return early and not touch UI or counters
    controller.handle_drop([])

    assert controller.active_jobs == 0
    assert controller.view.actionStopProcessing.enabled is False
    assert msgs == []


def test_decrement_active_jobs_no_action_with_view_none(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    controller.active_jobs = 1
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    controller._decrement_active_jobs()

    assert controller.active_jobs == 0
    assert any("Bereit" in m for m in msgs)
    # Ensure cancellation flag is reset even without a view/action
    assert controller._cancellation_requested is False


def test_close_calls_shutdown(monkeypatch):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    called = {"kwargs": None}
    def fake_shutdown(*args, **kwargs):
        called["kwargs"] = kwargs
    monkeypatch.setattr(controller.process_pool, "shutdown", fake_shutdown)

    controller.close()

    assert called["kwargs"] == {"wait": False, "cancel_futures": True}


def test_update_job_on_success_none_no_emit(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    emissions = []
    controller.jobUpdated.connect(lambda job: emissions.append(job))

    controller.update_job_on_success(None)

    assert emissions == []


def test_update_job_on_error_cancelled_and_error_emits_status(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    from aidocsynth.models.job import Job
    job = Job(path="/tmp/x.pdf")
    statuses: list[str] = []
    controller.jobUpdated.connect(lambda j: statuses.append(j.status))

    controller.update_job_on_error(job, asyncio.CancelledError())
    assert statuses[-1] == "cancelled"

    controller.update_job_on_error(job, RuntimeError("boom"))
    assert statuses[-1] == "error"


def test_decrement_active_jobs_resets_and_emits(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=ViewWithLabel())
    controller.active_jobs = 1
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    controller._decrement_active_jobs()

    assert controller.active_jobs == 0
    assert any("Bereit" in m for m in msgs)
    assert controller.view.actionStopProcessing.enabled is False
    assert controller._cancellation_requested is False


def test_decrement_active_jobs_updates_status_when_remaining(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=ViewWithLabel())
    controller.active_jobs = 2
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    controller._decrement_active_jobs()

    assert controller.active_jobs == 1
    assert any("1 Datei" in m for m in msgs)


@pytest.mark.asyncio
async def test_backup_file_handles_exception(monkeypatch):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    # Force backup to raise
    monkeypatch.setattr(controller.file_manager, "backup_original", lambda p: (_ for _ in ()).throw(RuntimeError("fail")))

    from aidocsynth.models.job import Job
    job = Job(path="/tmp/a.pdf")
    # Should not raise
    await controller._backup_file(job, Path(job.path))


@pytest.mark.asyncio
async def test_classify_document_cancelled_raises():
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    controller._cancellation_requested = True

    from aidocsynth.models.job import Job
    job = Job(path="/tmp/a.pdf")

    with pytest.raises(asyncio.CancelledError):
        await controller._classify_document(job, "TEXT", Path(job.path))


@pytest.mark.asyncio
async def test_pipeline_skips_metadata_when_no_new_path(monkeypatch):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)

    async def fake_extract(self, job, src):
        return "TEXT"
    async def fake_classify(self, job, txt, src):
        return ({"target_directory": "T", "target_filename": "x.txt"}, {})
    async def fake_process(self, job, src, cls):
        return None
    async def fail_generate(*args, **kwargs):
        raise AssertionError("generate_and_write_metadata should not be called when new_path is None")

    monkeypatch.setattr(MainController, "_extract_text_ocr", fake_extract)
    monkeypatch.setattr(MainController, "_classify_document", fake_classify)
    monkeypatch.setattr(MainController, "_process_file", fake_process)
    monkeypatch.setattr(MainController, "_generate_and_write_metadata", fail_generate)

    from aidocsynth.models.job import Job
    job = Job(path="/tmp/a.pdf")
    res = await controller._pipeline(job)

    assert res is job
    assert job.status == "done"


def test_show_about_dialog_exec_called(qtbot, monkeypatch):
    # Import locally to avoid global dependency
    from PySide6.QtWidgets import QApplication
    controller = MainController(config_manager=make_cfg("/tmp"), view=ViewWithLabel())

    class DummyDialog:
        executed = False
        def __init__(self, parent=None):
            self.parent = parent
        def exec(self):
            DummyDialog.executed = True

    # Ensure a QApplication exists and has no main_window attribute
    app = QApplication.instance() or QApplication([])
    if hasattr(app, "main_window"):
        delattr(app, "main_window")

    monkeypatch.setattr("aidocsynth.controllers.main_controller.AboutDialogView", DummyDialog)

    controller.show_about_dialog()

    assert DummyDialog.executed is True


def test_emit_processing_status_messages(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    controller.active_jobs = 1
    controller._emit_processing_status()
    controller.active_jobs = 3
    controller._emit_processing_status()

    assert any("Verarbeite 1 Datei" in m for m in msgs)
    assert any("Verarbeite 3 Dateien" in m for m in msgs)


def test_show_about_dialog_with_parent(qtbot, monkeypatch):
    # Import locally to avoid global dependency
    from PySide6.QtWidgets import QApplication
    controller = MainController(config_manager=make_cfg("/tmp"), view=ViewWithLabel())

    class DummyDialog:
        executed = False
        parent_seen = None
        def __init__(self, parent=None):
            DummyDialog.parent_seen = parent
        def exec(self):
            DummyDialog.executed = True

    # Ensure a QApplication exists and has a main_window attribute used as parent
    app = QApplication.instance() or QApplication([])
    prev_parent = getattr(app, "main_window", None)
    try:
        app.main_window = object()
        monkeypatch.setattr("aidocsynth.controllers.main_controller.AboutDialogView", DummyDialog)
        controller.show_about_dialog()
        assert DummyDialog.executed is True
        assert DummyDialog.parent_seen is app.main_window
    finally:
        if prev_parent is not None:
            app.main_window = prev_parent
        else:
            delattr(app, "main_window")


def test_handle_drop_emits_job_updated(monkeypatch, qtbot, tmp_path):
    # Import locally to avoid adding global imports
    from unittest.mock import AsyncMock
    from aidocsynth.models.job import Job
    controller = MainController(config_manager=make_cfg("/tmp"), view=ViewWithLabel())

    # Create a real temp file
    dummy_file = tmp_path / "test.pdf"
    dummy_file.write_text("x")

    # Ensure the worker's pipeline returns a Job so update_job_on_success emits jobUpdated
    monkeypatch.setattr(controller, "_pipeline", AsyncMock(return_value=Job(path=str(dummy_file))))

    # Wait for jobUpdated emitted via Worker completion path
    with qtbot.waitSignal(controller.jobUpdated, timeout=5000) as blocker:
        controller.handle_drop([str(dummy_file)])

    assert blocker.signal_triggered is True
    # Wait for cleanup to remove worker from the set
    qtbot.wait_until(lambda: len(controller.workers) == 0, timeout=5000)
    assert len(controller.workers) == 0


def test_open_working_directory_success(tmp_path, monkeypatch):
    # Existing directory
    d = tmp_path / "exists"; d.mkdir()
    controller = MainController(config_manager=make_cfg(d), view=ViewWithLabel())

    called = {"ok": False}
    def open_ok(url):
        called["ok"] = True
        return True
    monkeypatch.setattr("aidocsynth.controllers.main_controller.QDesktopServices.openUrl", open_ok)

    controller.open_working_directory()

    assert called["ok"] is True
    # No error message should be set on success
    assert controller.view.ocr_status_label.text == ""


def test_handle_settings_changed_noop_when_same_dir(tmp_path):
    # Track update_workdir_label calls to ensure no extra update when dir unchanged
    class TrackView(ViewWithLabel):
        def __init__(self):
            super().__init__()
            self.update_calls = 0
        def update_workdir_label(self, t: str):
            # Parent does not implement update_workdir_label; just record the call
            self.last_label = t
            self.update_calls += 1

    d = tmp_path / "w"; d.mkdir()
    cfg = AppSettings(); cfg.work_dir = d
    mock_cfg = MagicMock(); mock_cfg.data = cfg
    v = TrackView()
    controller = MainController(config_manager=mock_cfg, view=v)

    # After init, exactly one update
    assert v.update_calls == 1

    # Calling settings changed without changing directory should not call update again
    controller._handle_settings_changed()
    assert v.update_calls == 1


def test_emit_processing_status_messages(qtbot):
    controller = MainController(config_manager=make_cfg("/tmp"), view=None)
    msgs = []
    controller.ocr_status_changed.connect(lambda m: msgs.append(m))

    controller.active_jobs = 1
    controller._emit_processing_status()
    controller.active_jobs = 3
    controller._emit_processing_status()

    assert any("Verarbeite 1 Datei" in m for m in msgs)
    assert any("Verarbeite 3 Dateien" in m for m in msgs)
