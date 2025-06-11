import logging
import asyncio
import os
from pathlib import Path
from functools import partial
from concurrent.futures import ProcessPoolExecutor
from PySide6.QtCore import QObject, Signal, QThreadPool, Slot
from aidocsynth.models.job import Job
from aidocsynth.utils.worker     import Worker
from aidocsynth.services.settings_service import settings
from aidocsynth.services.file_manager     import backup_original, copy_sorted, copy_unsorted
from aidocsynth.services.text_pipeline    import full_text
from aidocsynth.services.providers.base   import get_provider
from aidocsynth.ui.about_dialog_view import AboutDialogView
from PySide6.QtWidgets import QApplication

class MainController(QObject):
    jobAdded = Signal(Job); jobUpdated = Signal(Job)
    ocr_status_changed = Signal(str) # message

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pool = QThreadPool.globalInstance()
        # Limit workers to avoid starving the system, leave one core for UI/OS
        max_proc = max(1, os.cpu_count() - 1)
        self.process_pool = ProcessPoolExecutor(max_workers=max_proc)
        self.active_jobs = 0
        self.workers = set()

    def close(self):
        """Shuts down the process pool gracefully on application exit."""
        self.logger.info("Shutting down process pool...")
        # Use wait=False and cancel_futures=True (Python 3.9+) to avoid blocking exit
        self.process_pool.shutdown(wait=False, cancel_futures=True)

    def handle_drop(self, paths):
        if not paths:
            return
        self.active_jobs += len(paths)
        self.logger.info(f"Received drop: {paths}, active jobs now: {self.active_jobs}")
        self.ocr_status_changed.emit(f"Verarbeite {len(paths)} Datei(en)...")
        for p in paths:
            job = Job(path=p)
            self.jobAdded.emit(job)
            worker = Worker(self._pipeline, job)

            # --- Robust Signal Handling ---
            # result: carries the completed job object on success
            # error: carries the exception on failure
            # finished: always emitted, used for cleanup
            worker.sig.result.connect(self.update_job_on_success)
            worker.sig.error.connect(partial(self.update_job_on_error, job))
            worker.sig.finished.connect(lambda _, w=worker: self._cleanup_after_worker(w))

            self.workers.add(worker)
            self.pool.start(worker)

    @Slot(object)
    def update_job_on_success(self, job):
        """Handles successful worker completion."""
        if job.status == "done":
            job.progress = 100
        self.jobUpdated.emit(job)

    def update_job_on_error(self, job, error):
        """Handles worker failure."""
        self.logger.error(f"Pipeline for job {job.path} failed.", exc_info=True)
        job.status = "error"
        self.jobUpdated.emit(job)

    def _cleanup_after_worker(self, worker):
        """Removes worker from the active set and decrements job counter."""
        if worker in self.workers:
            self.workers.remove(worker)
        self._decrement_active_jobs()

    def _decrement_active_jobs(self):
        """Decrements the counter for active jobs and updates status if all are done."""
        self.active_jobs -= 1
        self.logger.info(f"Job beendet, {self.active_jobs} aktive Jobs übrig")
        if self.active_jobs == 0:
            self.ocr_status_changed.emit("Bereit")

    async def _pipeline(self, job):
        cfg, src = settings.data, Path(job.path)
        self.logger.info(f"[{src.name}] Starting pipeline...")

        job.progress = 10; job.status = "backing up"; self.jobUpdated.emit(job)
        self.logger.info(f"[{src.name}] 1/5: Backing up original file...")
        backup_original(src, cfg)

        # In a real scenario, text extraction and OCR are separate steps.
        # Here, we combine them for simplicity.
        job.progress = 30; job.status = "extracting text"; self.jobUpdated.emit(job)
        self.logger.info(f"[{src.name}] 2/5: Extracting text (OCR)..." )
        # Run the CPU-bound OCR task in a separate process to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(self.process_pool, full_text, str(src))
        job.progress = 50; job.status = "ocr complete"; self.jobUpdated.emit(job)

        job.progress = 70; job.status = "classifying"; self.jobUpdated.emit(job)
        self.logger.info(f"[{src.name}] 3/5: Classifying document...")
        data = await get_provider(cfg.llm).classify_document({"content": text})
        self.logger.info(f"[{src.name}] -> Classification result: {data}")

        job.progress = 90; job.status = "sorting"; self.jobUpdated.emit(job)
        try:
            self.logger.info(f"[{src.name}] 4/5: Sorting file to '{data['targetPath']}' as '{data['fileName']}'...")
            copy_sorted(src, data["targetPath"], data["fileName"], cfg)
            job.status = "done"
            self.logger.info(f"[{src.name}] -> Success. Pipeline finished.")
        except Exception as e:
            self.logger.error(f"[{src.name}] -> Error during sorting: {e}. Moving to unsorted.", exc_info=True)
            copy_unsorted(src, cfg)
            job.status = "error"
            self.logger.info(f"[{src.name}] -> Finished with error.")
        return job

    def show_about_dialog(self):
        """
        Creates and displays the 'About' dialog.
        The dialog is modal to the main window if a parent is available,
        otherwise it's an application-modal dialog.
        """
        # Try to find a suitable parent window for modality
        parent_window = None
        if hasattr(QApplication.instance(), 'main_window') and QApplication.instance().main_window:
            parent_window = QApplication.instance().main_window
        
        dialog = AboutDialogView(parent=parent_window)
        dialog.exec()
