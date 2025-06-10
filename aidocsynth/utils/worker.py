from PySide6.QtCore import QRunnable, QObject, Signal
import asyncio, traceback

class WorkerSignals(QObject):
    finished = Signal(object)
    error    = Signal(str)

class Worker(QRunnable):
    def __init__(self, coro, *args):
        super().__init__()
        self.coro, self.args = coro, args
        self.sig = WorkerSignals()

    def run(self):
        try:
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            res  = loop.run_until_complete(self.coro(*self.args))
            self.sig.finished.emit(res)
        except Exception:
            self.sig.error.emit(traceback.format_exc())
