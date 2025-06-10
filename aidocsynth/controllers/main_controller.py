import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThreadPool
from aidocsynth.models.job import Job
from aidocsynth.utils.worker     import Worker
from aidocsynth.services.settings_service import settings
from aidocsynth.services.file_manager     import backup_original, move_sorted, move_unsorted
from aidocsynth.services.text_pipeline    import full_text
from aidocsynth.services.providers.base   import get_provider

class MainController(QObject):
    jobAdded = Signal(Job); jobUpdated = Signal(Job)
    def __init__(self): super().__init__(); self.pool = QThreadPool.globalInstance()
    def handle_drop(self, paths):
        for p in paths:
            job = Job(path=p); self.jobAdded.emit(job)
            w = Worker(self._pipeline, job); self.pool.start(w)
            w.sig.finished.connect(lambda _, j=job: self.jobUpdated.emit(j))
    async def _pipeline(self, job):
        cfg, src = settings.data, Path(job.path)
        backup_original(src, cfg)
        text = await full_text(src)
        data = get_provider(cfg.llm).classify_document({"content": text})
        data = await data
        try: move_sorted(src, data["targetPath"], data["fileName"], cfg); job.status="done"
        except Exception: move_unsorted(src, cfg); job.status="error"
