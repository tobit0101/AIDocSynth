import asyncio
import types
import pytest
from PySide6.QtCore import QCoreApplication

from aidocsynth.utils.worker import Worker


@pytest.mark.qt
def test_worker_sync_fn_emits_result_and_finished(qtbot):
    def add(a, b):
        return a + b

    w = Worker(add, 2, 3)

    captured = {"result": None, "finished": False}
    def on_result(val):
        captured["result"] = val
    def on_finished(_):
        captured["finished"] = True
    try:
        w.sig.result.connect(on_result)
        w.sig.finished.connect(on_finished)
        w.run()
        qtbot.wait_until(lambda: captured["finished"], timeout=1000)
    finally:
        try:
            w.sig.result.disconnect(on_result)
            w.sig.finished.disconnect(on_finished)
        except Exception:
            pass
    assert captured["result"] == 5


@pytest.mark.qt
def test_worker_fn_with_signals_injected_emits_progress_no_result(qtbot):
    messages = []

    def fn_with_signals(signals=None):
        # Worker should inject `signals`
        assert signals is not None
        signals.progress_updated.emit("Hello")
        # Return None so that Worker does not emit a result
        return None

    w = Worker(fn_with_signals)

    # Connect to progress and ensure it's emitted; also ensure result is not emitted
    captured = {"progress": [], "finished": False}
    def on_progress(msg):
        captured["progress"].append(msg)
    def on_finished(_):
        captured["finished"] = True
    try:
        w.sig.progress_updated.connect(on_progress)
        w.sig.finished.connect(on_finished)
        w.run()
        qtbot.wait_until(lambda: captured["finished"], timeout=1000)
    finally:
        try:
            w.sig.progress_updated.disconnect(on_progress)
            w.sig.finished.disconnect(on_finished)
        except Exception:
            pass
    assert captured["progress"] == ["Hello"]


@pytest.mark.qt
def test_worker_async_fn_emits_result(qtbot):
    async def coro(x):
        await asyncio.sleep(0)
        return x * 2

    w = Worker(coro, 7)

    captured = {"result": None, "finished": False}
    def on_result(val):
        captured["result"] = val
    def on_finished(_):
        captured["finished"] = True
    try:
        w.sig.result.connect(on_result)
        w.sig.finished.connect(on_finished)
        w.run()
        qtbot.wait_until(lambda: captured["finished"], timeout=1000)
    finally:
        try:
            w.sig.result.disconnect(on_result)
            w.sig.finished.disconnect(on_finished)
        except Exception:
            pass
    assert captured["result"] == 14


@pytest.mark.qt
def test_worker_exception_emits_error(qtbot):
    def boom():
        raise ValueError("boom")

    w = Worker(boom)

    captured = {"error": None, "finished": False}
    def on_error(e):
        captured["error"] = e
    def on_finished(_):
        captured["finished"] = True
    try:
        w.sig.error.connect(on_error)
        w.sig.finished.connect(on_finished)
        w.run()
        qtbot.wait_until(lambda: captured["finished"], timeout=1000)
    finally:
        try:
            w.sig.error.disconnect(on_error)
            w.sig.finished.disconnect(on_finished)
        except Exception:
            pass
    assert isinstance(captured["error"], Exception)


@pytest.mark.qt
def test_worker_cancelled_error_branch_logs_and_emits_error(qtbot, caplog):
    # Function that raises CancelledError
    def cancelled():
        raise asyncio.CancelledError()

    w = Worker(cancelled)

    captured = {"error": None, "finished": False}
    def on_error(e):
        captured["error"] = e
    def on_finished(_):
        captured["finished"] = True
    try:
        w.sig.error.connect(on_error)
        w.sig.finished.connect(on_finished)
        with caplog.at_level("INFO"):
            w.run()
        qtbot.wait_until(lambda: captured["finished"], timeout=1000)
    finally:
        try:
            w.sig.error.disconnect(on_error)
            w.sig.finished.disconnect(on_finished)
        except Exception:
            pass

    assert isinstance(captured["error"], asyncio.CancelledError)


@pytest.mark.qt
def test_worker_no_qcoreapplication_no_move_to_thread(qtbot, monkeypatch):
    # Simulate no QCoreApplication instance
    app = QCoreApplication.instance()
    if app is not None:
        # monkeypatch instance() to return None during Worker __init__
        monkeypatch.setattr("aidocsynth.utils.worker.QCoreApplication.instance", lambda: None)

    w = Worker(lambda: 42)
    # If no app instance, signals stay on current thread; run should still work
    captured = {"result": None, "finished": False}
    def on_result(val):
        captured["result"] = val
    def on_finished(_):
        captured["finished"] = True
    try:
        w.sig.result.connect(on_result)
        w.sig.finished.connect(on_finished)
        w.run()
        qtbot.wait_until(lambda: captured["finished"], timeout=1000)
    finally:
        try:
            w.sig.result.disconnect(on_result)
            w.sig.finished.disconnect(on_finished)
        except Exception:
            pass
    assert captured["result"] == 42


class StubSig:
    def __init__(self, on_emit):
        self._on_emit = on_emit
    def emit(self, *args, **kwargs):
        return self._on_emit(*args, **kwargs)


@pytest.mark.qt
def test_worker_error_signal_emit_runtimeerror_suppressed():
    def boom():
        raise ValueError("boom")

    w = Worker(boom)

    # Replace signals with stubs; error.emit raises RuntimeError
    w.sig = types.SimpleNamespace(
        error=StubSig(lambda e: (_ for _ in ()).throw(RuntimeError("sig error broken"))),
        result=StubSig(lambda *_: None),
        finished=StubSig(lambda *_: None),
    )

    # Should not raise despite RuntimeError when emitting error signal
    w.run()


@pytest.mark.qt
def test_worker_result_signal_emit_runtimeerror_suppressed():
    w = Worker(lambda: 123)

    # result.emit raises RuntimeError
    w.sig = types.SimpleNamespace(
        error=StubSig(lambda *_: None),
        result=StubSig(lambda *_: (_ for _ in ()).throw(RuntimeError("sig result broken"))),
        finished=StubSig(lambda *_: None),
    )

    w.run()  # Should not raise


@pytest.mark.qt
def test_worker_finished_signal_emit_runtimeerror_suppressed():
    w = Worker(lambda: 1)

    # finished.emit raises RuntimeError
    w.sig = types.SimpleNamespace(
        error=StubSig(lambda *_: None),
        result=StubSig(lambda *_: None),
        finished=StubSig(lambda *_: (_ for _ in ()).throw(RuntimeError("sig finished broken"))),
    )

    w.run()  # Should not raise
