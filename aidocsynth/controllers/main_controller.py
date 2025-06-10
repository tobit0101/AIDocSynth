import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThreadPool
from aidocsynth.models.job import Job
from aidocsynth.utils.worker     import Worker
from aidocsynth.services.settings_service import settings
from aidocsynth.services.file_manager     import backup_original, copy_sorted, copy_unsorted
from aidocsynth.services.text_pipeline    import full_text
from aidocsynth.services.providers.base   import get_provider

class MainController(QObject):
    jobAdded = Signal(Job); jobUpdated = Signal(Job)
    
    def __init__(self):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self.workers = set()

    def handle_drop(self, paths):
        for p in paths:
            job = Job(path=p)
            self.jobAdded.emit(job)
            worker = Worker(self._pipeline, job)
            # Connect to the result signal, which will carry the completed job object
            worker.sig.result.connect(lambda result, w=worker: self._on_worker_finished(w, result))
            self.workers.add(worker)
            self.pool.start(worker)

    def _on_worker_finished(self, worker, job):
        self.jobUpdated.emit(job)
        self.workers.remove(worker)

    async def _pipeline(self, job):
        cfg, src = settings.data, Path(job.path)
        print(f"\n[{src.name}] Starting pipeline...")

        print(f"[{src.name}] 1/4: Backing up original file...")
        backup_original(src, cfg)

        print(f"[{src.name}] 2/4: Extracting text...")
        text = await full_text(src)

        print(f"[{src.name}] 3/4: Classifying document...")
        data = await get_provider(cfg.llm).classify_document({"content": text})
        print(f"[{src.name}] -> Classification result: {data}")

        try:
            print(f"[{src.name}] 4/4: Sorting file to '{data['targetPath']}' as '{data['fileName']}'...")
            copy_sorted(src, data["targetPath"], data["fileName"], cfg)
            job.status = "done"
            print(f"[{src.name}] -> Success. Pipeline finished.")
        except Exception as e:
            print(f"[{src.name}] -> Error during sorting: {e}. Moving to unsorted.")
            copy_unsorted(src, cfg)
            job.status = "error"
            print(f"[{src.name}] -> Finished with error.")
        return job
