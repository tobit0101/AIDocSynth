from PySide6.QtCore import QObject, QRunnable, Signal, Slot
import asyncio
import inspect
import traceback
import logging

class WorkerSignals(QObject):
    finished = Signal(object)
    error    = Signal(Exception) 
    result   = Signal(object)
    progress_updated = Signal(str) # message

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.sig = WorkerSignals()

    @Slot()
    def run(self):
        """Executes the worker function, handling both sync and async functions.
        If the target function accepts a 'signals' keyword argument, the WorkerSignals instance is passed.
        """
        try:
            # Check if the target function expects a 'signals' argument
            fn_params = inspect.signature(self.fn).parameters
            if 'signals' in fn_params:
                self.kwargs['signals'] = self.sig

            if inspect.iscoroutinefunction(self.fn):
                # For async functions, run them in a new event loop
                result = asyncio.run(self.fn(*self.args, **self.kwargs))
            else:
                # For sync functions, run them directly
                result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            logging.exception("Error in worker thread")
            try:
                self.sig.error.emit(e)
            except RuntimeError:
                pass  # Signal source might be deleted
        else:
            try:
                self.sig.result.emit(result)
            except RuntimeError:
                pass  # Signal source might be deleted
        finally:
            try:
                self.sig.finished.emit(None)
            except RuntimeError:
                pass  # Signal source might be deleted
