from PySide6.QtCore import QObject, Slot

from aidocsynth.models.job import Job
from aidocsynth.ui.job_filter_proxy import JobFilterProxy
from aidocsynth.ui.job_table_model import JobTableModel
from aidocsynth.ui.status_dock_view import StatusDockView


class StatusDockController(QObject):
    def __init__(self, view: StatusDockView, parent=None):
        super().__init__(parent)
        self.view = view

        self._setup_model()
        self._connect_signals()

    def _setup_model(self):
        self.table_model = JobTableModel()
        self.proxy_model = JobFilterProxy(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.view.tblJobs.setModel(self.proxy_model)

        # Adjust column widths
        self.view.tblJobs.horizontalHeader().setStretchLastSection(True)
        self.view.tblJobs.resizeColumnToContents(0) # Datei
        self.view.tblJobs.resizeColumnToContents(1) # Status
        self.view.tblJobs.resizeColumnToContents(2) # Fortschritt

    def _connect_signals(self):
        self.view.cmbFilter.currentTextChanged.connect(self.proxy_model.set_filter_mode)

    @Slot(Job)
    def add_job(self, job: Job):
        self.table_model.add_job(job)

    @Slot(Job)
    def refresh_job(self, job: Job):
        self.table_model.refresh(job)
