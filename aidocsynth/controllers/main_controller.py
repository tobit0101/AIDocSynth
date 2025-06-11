import logging
import asyncio
import os
from pathlib import Path
from functools import partial
from concurrent.futures import ProcessPoolExecutor

from PySide6.QtCore import QObject, Signal, QThreadPool, Slot
from PySide6.QtWidgets import QApplication

from aidocsynth.models.job import Job
from aidocsynth.utils.worker import Worker
from aidocsynth.services.settings_service import settings
from aidocsynth.services.file_manager import backup_original, copy_sorted, copy_unsorted, get_directory_structure, sort_and_copy_document, get_file_metadata
from aidocsynth.services.text_pipeline import full_text
from aidocsynth.services.providers.base import get_provider
from aidocsynth.services.classification_service import ClassificationService
from aidocsynth.ui.about_dialog_view import AboutDialogView

class MainController(QObject):
    jobAdded = Signal(Job); jobUpdated = Signal(Job)
    ocr_status_changed = Signal(str) # message

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
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
        # This slot is called when the worker's result signal is emitted.
        # The job object is passed from the pipeline's return value.
        if job:
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

    async def _update_job_progress(self, job, progress, status_message, log_message_prefix=""):
        job.progress = progress
        job.status = status_message
        self.jobUpdated.emit(job)
        if log_message_prefix:
            src_name = Path(job.path).name
            self.logger.info(f"[{src_name}] {log_message_prefix}: {status_message}...")

    async def _backup_file(self, job, src_path):
        await self._update_job_progress(job, 10, "backing up", "1/5")
        backup_original(src_path, self.config_manager.data)

    async def _extract_text_ocr(self, job, src_path):
        await self._update_job_progress(job, 30, "extracting text", "2/5")
        # Run the CPU-bound OCR task in a separate process to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(self.process_pool, full_text, str(src_path))
        await self._update_job_progress(job, 50, "ocr complete")
        return text

    async def _classify_document(self, job, text_content):
        await self._update_job_progress(job, 70, "classifying", "3/5")
        llm_provider = None
        try:
            # 1. Get a new provider instance for this job.
            llm_provider = get_provider(self.config_manager.data.llm)

            # 2. Instantiate classification service
            classification_service = ClassificationService(llm_provider)

            # 3. Get directory structure for the prompt context
            work_dir = self.config_manager.data.work_dir
            dir_tuples = get_directory_structure(str(work_dir))
            # Format the directory structure with file counts for the prompt
            directory_structure = [f"{path} ({count} files)" for path, count in dir_tuples]

            # 4. Get file metadata
            file_metadata = get_file_metadata(Path(job.path))

            # 5. Call the service to perform classification
            classification_data = await classification_service.classify_document(
                text_content=text_content,
                file_path=job.path,
                metadata=file_metadata,
                directory_structure=directory_structure
            )

            src_name = Path(job.path).name
            self.logger.info(f"[{src_name}] -> Classification result: {classification_data}")
            return classification_data
        finally:
            # 5. Ensure the provider's resources are closed for this job.
            if llm_provider:
                await llm_provider.close()

    async def _sort_file(self, job, src_path, classification_data):
        await self._update_job_progress(job, 90, "sorting", "4/5")
        
        # Delegate sorting to the file manager service
        loop = asyncio.get_running_loop()
        job.status = await loop.run_in_executor(
            self.process_pool,
            sort_and_copy_document, 
            src_path, 
            classification_data, 
            self.config_manager.data
        )
        self.jobUpdated.emit(job)

    async def _pipeline(self, job):
        """The main processing pipeline for a single file."""
        src_path = Path(job.path)

        try:
            await self._backup_file(job, src_path)
            text_content = await self._extract_text_ocr(job, src_path)
            classification_data = await self._classify_document(job, text_content)
            await self._sort_file(job, src_path, classification_data)

            await self._update_job_progress(job, 100, "completed", "5/5")
            return job

        except Exception as e:
            self.logger.error(f"Pipeline failed for {src_path.name}: {e}", exc_info=True)
            self.update_job_on_error(job, str(e))

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
