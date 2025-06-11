import sys
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QFrame, QLabel, QProgressBar, QStatusBar, QWidget, QMenuBar
)
from PySide6.QtCore import Qt, QSize, QCoreApplication

from .drop_area import DropArea
from .status_dock_view import StatusDockView
from .settings_dialog_view import SettingsDialogView

class MainWindowView(QMainWindow):
    """
    Main application window view.
    The UI is created programmatically.
    """
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        self._setup_ui()
        self._create_actions()
        self._create_menus()
        self._connect_signals()

    def _setup_ui(self):
        # This code is migrated from the original main_window.ui file
        self.setWindowTitle("AI Doc Synth")
        if not self.objectName():
            self.setObjectName("MainWindow")
        self.resize(800, 600)

        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")

        self.dropFrame = QFrame(self.centralwidget)
        self.dropFrame.setObjectName("dropFrame")
        self.dropFrame.setMinimumSize(QSize(0, 180))
        self.dropFrame.setAcceptDrops(True)
        self.dropFrame.setFrameShape(QFrame.StyledPanel)
        self.dropFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.dropFrame)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout.addWidget(self.dropFrame)
        self.setCentralWidget(self.centralwidget)

        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.lblInfo = QLabel(self.statusbar)
        self.lblInfo.setObjectName("lblInfo")
        self.prgJob = QProgressBar(self.statusbar)
        self.prgJob.setObjectName("prgJob")
        self.prgJob.setValue(0)
        self.prgJob.setTextVisible(False)
        self.statusbar.addWidget(self.lblInfo)
        self.statusbar.addWidget(self.prgJob)
        self.setStatusBar(self.statusbar)

        # Explicitly create and set the menu bar for macOS compatibility
        self.menubar = QMenuBar(self)
        self.menubar.setNativeMenuBar(False) # Force menu bar inside the window on macOS
        self.setMenuBar(self.menubar)

        self._retranslate_ui()

        # Custom widget integration
        if self.dropFrame:
            if not self.dropFrame.layout():
                self.dropFrame.setLayout(QVBoxLayout())
            self.drop_area = DropArea()
            self.dropFrame.layout().addWidget(self.drop_area)
        else:
            print("FATAL: QFrame with name 'dropFrame' not found in the UI.", file=sys.stderr)
            self.drop_area = None

        # Create and add the status dock widget
        self.status_dock = StatusDockView(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.status_dock)

    def _retranslate_ui(self):
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "AIDocSynth", None))
        self.lblInfo.setText(QCoreApplication.translate("MainWindow", "Bereit", None))

    def _create_actions(self):
        """Create the application's actions."""
        self.actionSettings = QAction("&Einstellungen...", self)
        self.actionExit = QAction("&Beenden", self)
        self.actionExit.setShortcut("Ctrl+Q")
        self.actionToggleStatusDock = QAction("Statusleiste anzeigen", self)
        self.actionToggleStatusDock.setCheckable(True)
        self.actionToggleStatusDock.setChecked(True)

    def _create_menus(self):
        """Create the application's menu bar."""
        file_menu = self.menubar.addMenu("&Datei")
        file_menu.addAction(self.actionSettings)
        file_menu.addSeparator()
        file_menu.addAction(self.actionExit)
        view_menu = self.menubar.addMenu("&Ansicht")
        view_menu.addAction(self.actionToggleStatusDock)

    def _connect_signals(self):
        """Connect signals and slots."""
        self.actionSettings.triggered.connect(self.open_settings_dialog)
        self.actionExit.triggered.connect(self.close)
        self.actionToggleStatusDock.toggled.connect(self.status_dock.setVisible)
        if self.drop_area:
            self.drop_area.filesDropped.connect(self.controller.handle_drop)

    def open_settings_dialog(self):
        """Creates and shows the settings dialog."""
        dialog = SettingsDialogView(self)
        dialog.exec()
