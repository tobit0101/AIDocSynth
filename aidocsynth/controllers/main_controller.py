import json
import logging
from pathlib import Path
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
    ocr_status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pool = QThreadPool.globalInstance()
        self.active_jobs = 0
        self.workers = set()

    def handle_drop(self, paths):
        if not paths:
            return
        self.active_jobs += len(paths)
        self.logger.info(f"Received drop: {paths}, active jobs now: {self.active_jobs}")
        self.ocr_status_changed.emit(f"Processing {len(paths)} file(s)...")
        for p in paths:
            job = Job(path=p)
            self.jobAdded.emit(job)
            worker = Worker(self._pipeline, job)
            # Connect to the result signal, which will carry the completed job object
            worker.sig.result.connect(lambda result, w=worker: self._on_worker_finished(w, result))
            self.workers.add(worker)
            self.pool.start(worker)

    def _on_worker_finished(self, worker, job):
        if job.status == "done":
            job.progress = 100
        self.jobUpdated.emit(job)
        self.workers.remove(worker)
        self.handle_job_completion()

    @Slot()
    def handle_job_completion(self):
        self.active_jobs -= 1
        self.logger.info(f"Job completed, active jobs left: {self.active_jobs}")
        if self.active_jobs == 0:
            self.ocr_status_changed.emit("Ready")

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
        text = await full_text(src)
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
