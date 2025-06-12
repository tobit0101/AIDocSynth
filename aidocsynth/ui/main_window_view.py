import sys
import logging
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QFrame, QLabel, QStatusBar, QWidget, QMenuBar, QApplication, QStackedWidget
)
from PySide6.QtCore import Qt, QSize, QCoreApplication, Slot, QSettings, QPoint

from .drop_area import InactiveView, ActiveDropArea
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
        self.logger = logging.getLogger(self.__class__.__name__)

        self._setup_ui()
        self._create_actions()
        self._create_menus()
        self._connect_signals()

        self._load_settings()

    def _setup_ui(self):
        # This code is migrated from the original main_window.ui file
        self.setWindowTitle("AI Doc Synth")
        if not self.objectName():
            self.setObjectName("MainWindow")
        self.resize(400, 250)

        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")

        # NEW: Use QStackedWidget to manage active/inactive views
        self.drop_area_stack = QStackedWidget(self.centralwidget)
        self.drop_area_stack.setObjectName("dropAreaStack")
        self.drop_area_stack.setMinimumSize(QSize(0, 180))

        self.inactive_view = InactiveView()
        self.active_drop_area = ActiveDropArea()

        self.drop_area_stack.addWidget(self.inactive_view)
        self.drop_area_stack.addWidget(self.active_drop_area)
        
        self.verticalLayout.addWidget(self.drop_area_stack)
        self.setCentralWidget(self.centralwidget)

        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        # Add a permanent widget to the status bar for OCR status messages
        self.ocr_status_label = QLabel()
        self.statusbar.addPermanentWidget(self.ocr_status_label)

        # Explicitly create and set the menu bar for macOS compatibility
        self.menubar = QMenuBar(self)
        self.menubar.setNativeMenuBar(False) # Force menu bar inside the window on macOS
        self.setMenuBar(self.menubar)

        self._retranslate_ui()

        # Set initial state
        self.drop_area_stack.setCurrentWidget(self.inactive_view)
        self.logger.info("DropArea stack configured, showing inactive view.")
        
        # Create and add the status dock widget
        self.status_dock = StatusDockView(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.status_dock)
        self.status_dock.setVisible(False) # Hide by default

    def _retranslate_ui(self):
        # Set the main window title, this comment is to force re-compilation
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "AIDocSynth", None))

    def _create_actions(self):
        """Create the application's actions."""
        self.actionSettings = QAction("&Einstellungen...", self)
        self.actionExit = QAction("&Beenden", self)
        self.actionExit.setShortcut("Ctrl+Q")
        self.actionToggleStatusDock = QAction("Statusleiste anzeigen", self)
        self.actionToggleStatusDock.setCheckable(True)
        self.actionToggleStatusDock.setChecked(False)

        self.actionAbout = QAction(f"Über {QApplication.applicationName()}", self)

    def _create_menus(self):
        """Create the application's menu bar."""
        file_menu = self.menubar.addMenu("&Datei")
        file_menu.addAction(self.actionSettings)
        file_menu.addSeparator()
        file_menu.addAction(self.actionExit)
        view_menu = self.menubar.addMenu("&Ansicht")
        view_menu.addAction(self.actionToggleStatusDock)

        # Help Menu (Standard on Windows/Linux, macOS handles 'About' often in App menu)
        help_menu = self.menubar.addMenu("&Hilfe")
        help_menu.addAction(self.actionAbout)

    def _connect_signals(self):
        """Connect signals and slots."""
        self.actionSettings.triggered.connect(self.open_settings_dialog)
        self.actionExit.triggered.connect(QApplication.instance().quit)
        self.actionToggleStatusDock.toggled.connect(self.status_dock.setVisible)
        self.actionAbout.triggered.connect(self.controller.show_about_dialog)
        
        # NEW: Connect to the active drop area's signal
        self.active_drop_area.filesDropped.connect(self.controller.handle_drop)
        
        self.controller.ocr_status_changed.connect(self.update_ocr_status)
        self.controller.jobUpdated.connect(self.status_dock.update_job_progress)

    @Slot(str)
    def update_ocr_status(self, message):
        """Updates the OCR status label and switches the drop area view."""
        self.ocr_status_label.setText(f"OCR-Status: {message}")
        # The final ready signal is just "Bereit"
        is_ready = "Bereit" in message
        
        # NEW: Switch the view in the QStackedWidget
        if is_ready:
            self.drop_area_stack.setCurrentWidget(self.active_drop_area)
        else:
            self.drop_area_stack.setCurrentWidget(self.inactive_view)
            
        self.logger.info(f"OCR status: '{message}', Drop area ready: {is_ready}")

    def update_job_progress(self, job):
        """Updates the progress bar and status label for a job."""
        self.status_dock.update_job_progress(job)

    def open_settings_dialog(self):
        """Creates and shows the settings dialog."""
        from aidocsynth.controllers.settings_controller import SettingsController # Import here
        dialog = SettingsDialogView(self)
        controller = SettingsController(dialog) # Instantiate controller
        dialog.exec()

    def _init_window_position(self):
        """Set the initial window position based on the OS, with a margin."""
        margin = 20  # Margin from the screen corner in pixels
        screen_geometry = QApplication.primaryScreen().availableGeometry()

        # Position window in the top-right corner on macOS
        if sys.platform == "darwin":
            # Calculate top-right position and apply margin
            top_right_point = screen_geometry.topRight() - self.frameGeometry().topRight()
            # Move left by margin, and down by margin + menu bar height
            top_right_point += QPoint(-margin, margin + self.menuBar().height())
            self.move(top_right_point)
        # Position window in the bottom-right corner on other systems (e.g., Windows)
        else:
            # Calculate bottom-right position and apply margin
            bottom_right_point = screen_geometry.bottomRight() - self.frameGeometry().bottomRight()
            # Move left by margin, and up by margin
            bottom_right_point += QPoint(-margin, -margin)
            self.move(bottom_right_point)

    def _load_settings(self):
        """Load window size, position, and state from QSettings."""
        settings = QSettings()
        geometry = settings.value("geometry")
        state = settings.value("windowState")

        if geometry:
            self.restoreGeometry(geometry)
        else:
            # No settings found, set initial position
            self._init_window_position()

        if state:
            self.restoreState(state)

    def _save_settings(self):
        """Save window size, position, and state to QSettings."""
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())


    def closeEvent(self, event: QCloseEvent):
        """
        Override the close event to hide the window instead of closing it.
        The application will keep running in the system tray.
        """
        self._save_settings()
        event.ignore()
        self.hide()
