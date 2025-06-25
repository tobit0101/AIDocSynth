import logging
import asyncio
import os
from pathlib import Path
from functools import partial
from concurrent.futures import ProcessPoolExecutor

from PySide6.QtCore import QObject, Signal, QThreadPool, Slot, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDesktopServices

from aidocsynth.models.job import Job
from aidocsynth.utils.worker import Worker
from aidocsynth.services.settings_service import settings
from aidocsynth.services.file_manager import FileManager
from aidocsynth.services.text_pipeline import full_text
from aidocsynth.services.providers.base import get_provider
from aidocsynth.services.classification_service import ClassificationService
from aidocsynth.services.metadata_service import MetadataService, write_metadata_task
from aidocsynth.ui.about_dialog_view import AboutDialogView


class MainController(QObject):
    jobAdded = Signal(Job); jobUpdated = Signal(Job)
    ocr_status_changed = Signal(str) # message

    def __init__(self, config_manager, view): # Added view parameter
        super().__init__()
        self.config_manager = config_manager
        self.view = view # Store view reference
        self._current_work_dir_display = "" # Store current displayed path
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pool = QThreadPool.globalInstance()
        # Limit workers to avoid starving the system, leave one core for UI/OS
        max_proc = max(1, os.cpu_count() - 1)
        self.process_pool = ProcessPoolExecutor(max_workers=max_proc)
        self.active_jobs = 0
        self.workers = set()
        self.file_manager = FileManager(self.config_manager.data)
        self._cancellation_requested = False

        # Initialize working directory label in the view
        if self.view and hasattr(self.view, 'update_workdir_label'):
            initial_work_dir = str(self.config_manager.data.work_dir)
            self.view.update_workdir_label(initial_work_dir)
            self._current_work_dir_display = initial_work_dir

        # Connect to settings changes
        if hasattr(self.config_manager, 'settings_changed'):
            self.config_manager.settings_changed.connect(self._handle_settings_changed)

        # Set initial thread pool size based on settings
        self._update_thread_pool_size()

    def close(self):
        """Shuts down the process pool gracefully on application exit."""
        self.logger.info("Shutting down process pool...")
        # Use wait=False and cancel_futures=True (Python 3.9+) to avoid blocking exit
        self.process_pool.shutdown(wait=False, cancel_futures=True)

    def handle_drop(self, paths):
        if not paths:
            return

        # Reset cancellation flag and enable stop button if jobs are starting
        if paths:
            self._cancellation_requested = False
            if self.view and hasattr(self.view, 'actionStopProcessing'):
                self.view.actionStopProcessing.setEnabled(True)

        self.active_jobs += len(paths)
        self.logger.info(f"Received drop: {paths}, active jobs now: {self.active_jobs}")
        # Inform UI about total number of active jobs
        self._emit_processing_status()
        for p in paths:
            if self._cancellation_requested:
                self.logger.info("Cancellation requested, skipping remaining files in this batch.")
                # Adjust active_jobs count for the skipped files.
                try:
                    current_index = paths.index(p) # Get the index of the current path
                    skipped_count = len(paths) - current_index
                    self.active_jobs -= skipped_count
                    self.logger.info(f"Skipped {skipped_count} files due to cancellation. Active jobs now: {self.active_jobs}")
                    if self.active_jobs <= 0: # Use <= 0 for safety
                        self.active_jobs = 0 # Ensure it's not negative
                        self.ocr_status_changed.emit("Bereit")
                        if self.view and hasattr(self.view, 'actionStopProcessing'):
                            self.view.actionStopProcessing.setEnabled(False)
                        # self._cancellation_requested is already True and will be reset if a new batch starts or all jobs truly finish
                    else:
                        self._emit_processing_status() # Update status with new active_jobs count
                except ValueError:
                    # This should ideally not happen if p is from paths list
                    self.logger.warning(f"Path {p} not found in paths list during cancellation handling.")
                break # Exit the loop, stop processing further files from this batch
            
            job = Job(path=p)
            self.jobAdded.emit(job)
            worker = Worker(self._pipeline, job)

            # --- Robust Signal Handling ---
            worker.sig.result.connect(self.update_job_on_success)
            worker.sig.error.connect(partial(self.update_job_on_error, job))
            worker.sig.finished.connect(lambda _, w=worker: self._cleanup_after_worker(w))

            # The QThreadPool will manage serial vs parallel execution based on its maxThreadCount.
            self.logger.info(f"Queueing job for {p} for processing.")
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
        """Handles worker failure, including cancellation."""
        if isinstance(error, asyncio.CancelledError):
            self.logger.info(f"Job {job.path} was cancelled by user request.")
            if job.status != "cancelled": # Should have been set prior, but ensure
                job.status = "cancelled"
                self.jobUpdated.emit(job)
            # No further error logging needed as this is an expected outcome
        else:
            self.logger.error(f"Pipeline for job {job.path} failed.", exc_info=error)
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
            if self.view and hasattr(self.view, 'actionStopProcessing'):
                self.view.actionStopProcessing.setEnabled(False)
            self._cancellation_requested = False # Reset for next batch
        else:
            # Update the UI with remaining job count
            self._emit_processing_status()

    async def _update_job_progress(self, job, progress, status, log_message_prefix="", result=None):
        """Helper to update job progress and emit signals."""
        if self._cancellation_requested:
            self.logger.info(f"Cancellation requested, setting job {job.path} to 'cancelled'")
            job.status = "cancelled"
            self.jobUpdated.emit(job)
            raise asyncio.CancelledError(f"Processing cancelled by user for {job.path}.")

        job.progress = progress
        job.status = status
        if result is not None:
            job.result = result
        self.jobUpdated.emit(job)
        if log_message_prefix:
            self.logger.info(f"[{Path(job.path).name}] {log_message_prefix}: {status}...")

    async def _backup_file(self, job, src_path):
        await self._update_job_progress(job, 10, "backing up", "1/5")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.process_pool, self.file_manager.backup_original, src_path
        )

    async def _extract_text_ocr(self, job, src_path):
        await self._update_job_progress(job, 30, "extracting text", "2/5")
        # Run the CPU-bound OCR task in a separate process to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(self.process_pool, full_text, str(src_path))
        await self._update_job_progress(job, 50, "ocr complete")
        return text

    async def _classify_document(self, job, text_content, src_path):
        if self._cancellation_requested:
            self.logger.info(f"Cancellation requested before starting classification for {job.path}.")
            raise asyncio.CancelledError(f"Classification for {job.path} cancelled by user request.")
        
        await self._update_job_progress(job, 70, "classifying", "3/6") # This also checks cancellation
        llm_provider = None
        try:
            llm_provider = get_provider(self.config_manager.data.llm)
            classification_service = ClassificationService(llm_provider)
            loop = asyncio.get_running_loop()
            metadata_service = MetadataService()

            directory_structure, original_metadata = await asyncio.gather(
                loop.run_in_executor(self.process_pool, self.file_manager.get_formatted_directory_structure),
                loop.run_in_executor(self.process_pool, metadata_service.get_file_metadata, src_path)
            )

            classification_data = await classification_service.classify_document(
                text_content=text_content,
                file_path=job.path,
                metadata=original_metadata,
                directory_structure=directory_structure,
                is_cancelled_callback=lambda: self._cancellation_requested
            )

            src_name = Path(job.path).name
            self.logger.info(f"[{src_name}] -> Classification result: {classification_data}")
            return classification_data, original_metadata
        finally:
            if llm_provider:
                await llm_provider.close()

    async def _process_file(self, job, src_path, classification_data):
        await self._update_job_progress(job, 90, "processing", "4/6")
        loop = asyncio.get_running_loop()
        new_path = await loop.run_in_executor(
            self.process_pool,
            self.file_manager.process_document, 
            src_path, 
            classification_data
        )
        return new_path

    async def _generate_and_write_metadata(self, job, new_path, classification_data, original_metadata):
        await self._update_job_progress(job, 95, "writing metadata", "5/6")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.process_pool,
            write_metadata_task,
            new_path,
            classification_data,
            original_metadata
        )

    @Slot()
    def request_cancellation(self):
        """Requests cancellation of ongoing and pending processing tasks."""
        self.logger.info("Cancellation requested by user.")
        self.ocr_status_changed.emit("Stoppen...") # Update status immediately
        self._cancellation_requested = True
        if self.view and hasattr(self.view, 'actionStopProcessing'):
            self.view.actionStopProcessing.setEnabled(False) # Disable button once clicked

        # For QThreadPool, we can't directly cancel QRunnables that are already running.
        # The pipeline itself will need to check self._cancellation_requested.
        # We can, however, try to clear pending tasks if QThreadPool supports it (it doesn't directly).
        # self.pool.clear() # This method doesn't exist on QThreadPool
        # self.pool.waitForDone(100) # Attempt to let current finish quickly, then rely on flag

        # For ProcessPoolExecutor, futures can be cancelled if not yet running.
        # However, our tasks are submitted one by one inside the async pipeline steps.
        # The primary mechanism will be the _pipeline checking the flag.

        # If in serial mode and a worker.run() is blocking, this flag will be checked by the next iteration
        # or by the pipeline steps of the currently running serial task.

    async def _pipeline(self, job):
        """The main processing pipeline for a single file."""
        if self._cancellation_requested:
            self.logger.info(f"Pipeline for job {job.path} cancelled before starting.")
            job.status = "cancelled"
            job.progress = 0 # Or current progress if preferred for cancelled state
            self.jobUpdated.emit(job)
            # Ensure this is handled by the worker's error path to decrement active_jobs
            raise asyncio.CancelledError(f"Processing cancelled by user before pipeline start for {job.path}.")

        src_path = Path(job.path)

        try:
            await self._backup_file(job, src_path)
            text_content = await self._extract_text_ocr(job, src_path)
            classification_data, original_metadata = await self._classify_document(job, text_content, src_path)
            
            new_path = await self._process_file(job, src_path, classification_data)

            if new_path:
                await self._generate_and_write_metadata(job, new_path, classification_data, original_metadata)

            # Pass the new path to the final status update so it can be displayed in the UI
            await self._update_job_progress(job, 100, "done", "6/6", result=str(new_path) if new_path else "")
            return job

        except asyncio.CancelledError as e:
            self.logger.info(f"Pipeline for {src_path.name} was cancelled: {e}")
            # Job status should have been set to 'cancelled' by _update_job_progress or pipeline start check
            # Ensure update_job_on_error or a similar mechanism handles this for cleanup if not already done
            # For now, assuming the job status is already 'cancelled' and sig.error will be emitted by worker.
            # We might need a specific slot for cancellation if different UI update is needed.
            # Re-raise to ensure worker's error path is taken for cleanup.
            if job.status != "cancelled": # If not already set by our checks
                job.status = "cancelled"
                self.jobUpdated.emit(job)
            raise # Important to re-raise for Worker's error handling
        except Exception as e:
            self.logger.error(f"Pipeline failed for {src_path.name}: {e}", exc_info=True)
            self.update_job_on_error(job, str(e)) # This will set job.status = "error"

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

    def open_working_directory(self):
        """Opens the configured working directory in the system's file explorer."""
        work_dir_path = str(self.config_manager.data.work_dir)
        self.logger.info(f"Attempting to open working directory: {work_dir_path}")
        if not os.path.exists(work_dir_path):
            self.logger.warning(f"Working directory does not exist: {work_dir_path}")
            # Optionally, inform the user via a status bar message or dialog
            # For now, just log a warning.
            if self.view and hasattr(self.view, 'ocr_status_label'): # Use ocr_status_label for temp messages
                 self.view.ocr_status_label.setText(f"Fehler: Arbeitsverzeichnis nicht gefunden: {work_dir_path}")
            return
        
        url = QUrl.fromLocalFile(work_dir_path)
        if not QDesktopServices.openUrl(url):
            self.logger.error(f"Failed to open working directory: {work_dir_path}")
            # Optionally, inform the user
            if self.view and hasattr(self.view, 'ocr_status_label'):
                 self.view.ocr_status_label.setText(f"Fehler: Konnte Arbeitsverzeichnis nicht öffnen: {work_dir_path}")

    @Slot()
    def _handle_settings_changed(self):
        """Handles the settings_changed signal from SettingsService."""
        new_work_dir = str(self.config_manager.data.work_dir)
        if new_work_dir != self._current_work_dir_display:
            self.logger.info(f"Working directory changed from '{self._current_work_dir_display}' to '{new_work_dir}'. Updating label.")
            if self.view and hasattr(self.view, 'update_workdir_label'):
                self.view.update_workdir_label(new_work_dir)
                self._current_work_dir_display = new_work_dir
        else:
            self.logger.debug("Settings changed, but working directory remains the same.")

        # Update thread pool size in case processing mode changed
        self._update_thread_pool_size()

    def _update_thread_pool_size(self):
        """Sets the max thread count on the global QThreadPool based on the processing mode setting."""
        if settings.data.processing_mode == "serial":
            self.pool.setMaxThreadCount(1)
            self.logger.info("Set QThreadPool max threads to 1 for serial processing.")
        else:  # Parallel processing
            # Set to a reasonable number of threads for parallel processing.
            # os.cpu_count() is a good default.
            max_threads = os.cpu_count()
            self.pool.setMaxThreadCount(max_threads)
            self.logger.info(f"Set QThreadPool max threads to {max_threads} for parallel processing.")

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------
    def _emit_processing_status(self):
        """Emit a human-readable processing status based on active_jobs."""
        if self.active_jobs == 1:
            msg = "Verarbeite 1 Datei..."
        else:
            msg = f"Verarbeite {self.active_jobs} Dateien..."
        self.ocr_status_changed.emit(msg)
