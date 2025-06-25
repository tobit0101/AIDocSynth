from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTableView, QProgressBar, QLabel, QHBoxLayout, QComboBox, QHeaderView
)
from PySide6.QtCore import QCoreApplication, Slot, QModelIndex, QUrl, Qt, QTimer

import os
from PySide6.QtGui import QDesktopServices

from .elide_delegate import ElideDelegate
from .clickable_table_view import ClickableTableView

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

        # Filter Area
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        self.lblFilter = QLabel("Filter:")
        self.cmbFilter = QComboBox()
        self.cmbFilter.setObjectName("cmbFilter")
        self.cmbFilter.addItems(["Alle", "Aktiv", "Abgeschlossen"])
        filter_layout.addWidget(self.lblFilter)
        filter_layout.addWidget(self.cmbFilter, 1)
        self.verticalLayout.addWidget(filter_widget)

        self.tblJobs = ClickableTableView(self.dockWidgetContents)
        self.tblJobs.setObjectName("tblJobs")
        # Columns are now 1-indexed due to the new icon column at 0
        self.tblJobs.add_clickable_column(1) # 'Datei' column
        self.tblJobs.add_clickable_column(4) # 'Ergebnis' column

        # Apply custom delegate for eliding file paths from the left
        elide_delegate = ElideDelegate(self.tblJobs)
        self.tblJobs.setItemDelegateForColumn(1, elide_delegate) # 'Datei' column
        self.tblJobs.setItemDelegateForColumn(4, elide_delegate) # 'Ergebnis' column

        self.verticalLayout.addWidget(self.tblJobs)
        self.setWidget(self.dockWidgetContents)

        self.tblJobs.clicked.connect(self.on_table_clicked)

        # Defer column configuration to avoid timing issues with layout initialization.
        QTimer.singleShot(0, self._configure_table_columns)

    def _configure_table_columns(self):
        """Configures column widths for a smart but fully interactive layout."""
        header = self.tblJobs.horizontalHeader()

        # Set resize modes: Fixed for icon, Interactive for the rest
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)

        # Calculate and set initial widths
        icon_width = 30
        status_width = 100
        progress_width = 80

        self.tblJobs.setColumnWidth(0, icon_width)
        self.tblJobs.setColumnWidth(2, status_width)
        self.tblJobs.setColumnWidth(3, progress_width)

        available_width = self.tblJobs.viewport().width()
        remaining_width = max(0, available_width - icon_width - status_width - progress_width)
        stretch_width = remaining_width // 2

        self.tblJobs.setColumnWidth(1, stretch_width)    # Datei
        self.tblJobs.setColumnWidth(4, stretch_width)    # Ergebnis

    def _retranslate_ui(self):
        self.setWindowTitle(QCoreApplication.translate("dockStatus", "Status", None))

    @Slot(QModelIndex)
    def on_table_clicked(self, index):
        """Handles clicks on the table view."""
        # Adjusted for new column layout: 1='Datei', 4='Ergebnis'
        if index.column() in [1, 4]:
            model = self.tblJobs.model()
            path_data = model.data(index, Qt.DisplayRole)

            if path_data and os.path.exists(path_data):
                # Open the directory containing the file
                dir_path = os.path.dirname(path_data)
                QDesktopServices.openUrl(QUrl.fromLocalFile(dir_path))
