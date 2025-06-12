from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QCoreApplication
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
        # Ensure the signals object lives in the main (GUI) thread to prevent
        # destruction from the worker thread which can lead to Qt semaphore
        # leaks and segmentation faults.
        main_thread = QCoreApplication.instance().thread() if QCoreApplication.instance() else None
        if main_thread:
            self.sig.moveToThread(main_thread)

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
                # Emit result only if the function returned a meaningful value. If the
                # function handled its own signal emission (common when it receives a
                # `signals` argument), it will usually return `None`, so we avoid
                # emitting `None` again to prevent duplicate emissions that can break
                # downstream unpacking logic.
                if result is not None:
                    self.sig.result.emit(result)
            except RuntimeError:
                pass  # Signal source might be deleted
        finally:
            try:
                self.sig.finished.emit(None)
            except RuntimeError:
                pass  # Signal source might be deleted
