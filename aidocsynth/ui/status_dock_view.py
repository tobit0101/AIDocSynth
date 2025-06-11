from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTableView
)
from PySide6.QtCore import QCoreApplication

class StatusDockView(QDockWidget):
    """
    Status dock widget view.
    The UI is created programmatically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()



    def _setup_ui(self):
        # This code is migrated from the original status_dock.ui file
        if not self.objectName():
            self.setObjectName("dockStatus")
        self.dockWidgetContents = QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout = QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tblJobs = QTableView(self.dockWidgetContents)
        self.tblJobs.setObjectName("tblJobs")
        self.verticalLayout.addWidget(self.tblJobs)
        self.setWidget(self.dockWidgetContents)

        self._retranslate_ui()

    def _retranslate_ui(self):
        self.setWindowTitle(QCoreApplication.translate("dockStatus", "Status", None))
