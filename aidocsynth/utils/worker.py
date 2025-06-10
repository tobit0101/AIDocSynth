from PySide6.QtCore import QObject, QRunnable, Signal, Slot
import asyncio
import inspect
import traceback

class WorkerSignals(QObject):
    finished = Signal(object)
    error    = Signal(str)
    result   = Signal(object)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.sig = WorkerSignals()

    @Slot()
    def run(self):
        try:
            if inspect.iscoroutinefunction(self.fn):
                loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.fn(*self.args, **self.kwargs))
            else:
                result = self.fn(*self.args, **self.kwargs)
            self.sig.result.emit(result)
        except Exception as e:
            self.sig.error.emit(str(e))
        finally:
            self.sig.finished.emit(None)
