from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTableView, QProgressBar, QLabel, QHBoxLayout
)
from PySide6.QtCore import QCoreApplication, Slot

class StatusDockView(QDockWidget):
    """
    Status dock widget view.
    The UI is created programmatically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    @Slot(object)
    def update_job_progress(self, job):
        """Updates the progress bar and status label for a single job."""
        self.prgJob.setValue(job.progress)
        self.lblJobStatus.setText(f"{job.status.capitalize()}...")

    def _setup_ui(self):
        # This code is migrated from the original status_dock.ui file
        if not self.objectName():
            self.setObjectName("dockStatus")
        self.dockWidgetContents = QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout = QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout.setObjectName("verticalLayout")
        # Progress Area
        progress_widget = QWidget()
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.lblJobStatus = QLabel("Ready")
        self.prgJob = QProgressBar()
        self.prgJob.setObjectName("prgJob")
        self.prgJob.setRange(0, 100)
        self.prgJob.setValue(0)
        progress_layout.addWidget(self.lblJobStatus)
        progress_layout.addWidget(self.prgJob, 1) # Add stretch factor
        self.verticalLayout.addWidget(progress_widget)

        self.tblJobs = QTableView(self.dockWidgetContents)
        self.tblJobs.setObjectName("tblJobs")
        self.verticalLayout.addWidget(self.tblJobs)
        self.setWidget(self.dockWidgetContents)

        self._retranslate_ui()

    def _retranslate_ui(self):
        self.setWindowTitle(QCoreApplication.translate("dockStatus", "Status", None))
