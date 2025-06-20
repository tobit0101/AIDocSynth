import sys
import logging
from PySide6.QtGui import QAction, QCloseEvent, QShowEvent, QResizeEvent
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QFrame, QLabel, QStatusBar, QWidget, QMenuBar, QApplication, QStackedWidget, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QCoreApplication, Slot, QSettings, QPoint, QDir
from PySide6.QtGui import QDesktopServices

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
        self._retranslate_ui() # Call after actions and menus are created
        self._connect_local_signals() # Connect signals not dependent on controller

        # Flag to track if OCR engine initialization is finished
        self.ocr_initialized = False

        self._load_settings()

        self._current_raw_work_dir: str | None = None # Store the full path for re-eliding

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
        self.workdir_label = QLabel()
        self.workdir_label.setToolTip(QCoreApplication.translate("MainWindow", "Klicken, um das Arbeitsverzeichnis zu öffnen", None))
        self.workdir_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.workdir_label.setCursor(Qt.CursorShape.PointingHandCursor) # Set pointing hand cursor
        self.statusbar.addWidget(self.workdir_label, 1) # Add to the left with stretch factor 1
        self.statusbar.addPermanentWidget(self.ocr_status_label) # This one stays on the right

        # Explicitly create and set the menu bar for macOS compatibility
        self.menubar = QMenuBar(self)
        self.menubar.setNativeMenuBar(False) # Force menu bar inside the window on macOS
        self.setMenuBar(self.menubar)

        # Set initial state
        self.drop_area_stack.setCurrentWidget(self.inactive_view)
        self.logger.info("DropArea stack configured, showing inactive view.")
        
        # Create and add the status dock widget
        self.status_dock = StatusDockView(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.status_dock)
        self.status_dock.setVisible(False) # Hide by default

    @Slot()
    def show_and_raise(self):
        """Shows the main window, ensures it's not minimized, and raises it to the front."""
        self.logger.info("Attempting to show and raise main window.")
        if self.isHidden():
            self.show()
        
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        
        self.raise_() # Bring window to the front
        self.activateWindow() # Set focus to the window
        self.logger.info("Main window shown and raised.")

    def _retranslate_ui(self):
        # Set the main window title, this comment is to force re-compilation
        self.setWindowTitle(QCoreApplication.translate("MainWindow", "AIDocSynth", None))
        self.actionOpenWorkdir.setText(QCoreApplication.translate("MainWindow", "&Arbeitsverzeichnis öffnen...", None))
        self.actionStopProcessing.setText(QCoreApplication.translate("MainWindow", "Prozess &stoppen", None))
        self.workdir_label.setToolTip(QCoreApplication.translate("MainWindow", "Klicken, um das Arbeitsverzeichnis zu öffnen", None))

    def _create_actions(self):
        """Create the application's actions."""
        self.actionSettings = QAction("&Einstellungen...", self)
        self.actionExit = QAction("&Beenden", self)
        self.actionExit.setShortcut("Ctrl+Q")
        self.actionToggleStatusDock = QAction("Statusleiste anzeigen", self)
        self.actionToggleStatusDock.setCheckable(True)
        self.actionToggleStatusDock.setChecked(False)

        self.actionAbout = QAction(f"Über {QApplication.applicationName()}", self)
        self.actionShowMainWindow = QAction(QCoreApplication.translate("MainWindow", "&Hauptfenster anzeigen", None), self)
        self.actionOpenWorkdir = QAction("&Arbeitsverzeichnis öffnen...", self)
        self.actionStopProcessing = QAction("Prozess &stoppen", self)
        self.actionStopProcessing.setEnabled(False) # Initially disabled

    def _create_menus(self):
        """Create the application's menu bar."""
        file_menu = self.menubar.addMenu("&Datei")
        file_menu.addAction(self.actionSettings)
        file_menu.addAction(self.actionStopProcessing)
        file_menu.addSeparator()
        file_menu.addAction(self.actionExit)
        view_menu = self.menubar.addMenu("&Ansicht")
        view_menu.addAction(self.actionToggleStatusDock)
        view_menu.addSeparator()
        view_menu.addAction(self.actionOpenWorkdir)

        # Help Menu (Standard on Windows/Linux, macOS handles 'About' often in App menu)
        help_menu = self.menubar.addMenu("&Hilfe")
        help_menu.addAction(self.actionAbout)

    def _connect_local_signals(self):
        """Connect signals and slots that don't depend on the controller."""
        self.actionSettings.triggered.connect(self.open_settings_dialog)
        self.actionExit.triggered.connect(QApplication.instance().quit)
        self.actionToggleStatusDock.toggled.connect(self.status_dock.setVisible)
        self.actionShowMainWindow.triggered.connect(self.show_and_raise)
        self.actionOpenWorkdir.triggered.connect(self._handle_open_workdir_request)
        self.workdir_label.mousePressEvent = self._handle_open_workdir_request
        # self.actionStopProcessing will be connected in connect_controller_signals

    def connect_controller_signals(self):
        """Connect signals that depend on the controller. Call after controller is set."""
        if not self.controller:
            self.logger.error("Controller not set, cannot connect controller signals.")
            return
        self.actionAbout.triggered.connect(self.controller.show_about_dialog)
        self.active_drop_area.filesDropped.connect(self.controller.handle_drop)
        self.controller.ocr_status_changed.connect(self.update_ocr_status)
        self.controller.jobUpdated.connect(self.status_dock.update_job_progress)
        self.actionStopProcessing.triggered.connect(self.controller.request_cancellation) # Connect stop action

    @Slot(str)
    def update_ocr_status(self, message):
        """Updates the OCR status label and manages drag-and-drop availability.

        The drop area is disabled only while the OCR engine is being initialised.
        After the first "Bereit" signal the area remains enabled, allowing additional
        files to be dropped even while other jobs are still processing.
        """
        self.ocr_status_label.setText(message)
        self.ocr_status_label.setToolTip(message) # Also set tooltip for very long messages

        # After the OCR engine signals readiness once, keep the drop area active.
        if not self.ocr_initialized:
            if "Bereit" in message:
                # Initialisation finished -> enable drag & drop
                self.ocr_initialized = True
                self.drop_area_stack.setCurrentWidget(self.active_drop_area)
            else:
                # Still initialising -> keep disabled
                self.drop_area_stack.setCurrentWidget(self.inactive_view)
        # If already initialised, never block the drop area again

        self.logger.info(f"OCR status: '{message}', OCR initialised: {self.ocr_initialized}")

    def update_job_progress(self, job):
        """Updates the progress bar and status label for a job."""
        self.status_dock.update_job_progress(job)

    @Slot(str)
    def update_workdir_label(self, path: str):
        """Updates the working directory label in the status bar, eliding if necessary."""
        self._current_raw_work_dir = path  # Store the full path

        if not self.workdir_label.isVisible() or not self._current_raw_work_dir:
            self.workdir_label.setText("") # Clear if not visible or no path
            return

        font_metrics = self.workdir_label.fontMetrics()
        # A small margin so text doesn't touch the very edge of the label area if it's small.
        # This doesn't enforce a minimum width for the label itself, only for the text area within it.
        elide_margin = 5 

        # The available width for eliding is the label's current actual width, less a small margin.
        # The QSizePolicy.Expanding and stretch factor on workdir_label, and ocr_status_label
        # being a permanent widget, should ensure workdir_label gets the correct residual width.
        available_width_for_text = self.workdir_label.width() - elide_margin
        
        # elidedText will handle small/zero widths appropriately (e.g. returning "..." or "").
        # We ensure it's not negative.
        final_elided_path = font_metrics.elidedText(
            self._current_raw_work_dir,
            Qt.TextElideMode.ElideMiddle,
            max(0, available_width_for_text) 
        )
        self.workdir_label.setText(final_elided_path)
        self.workdir_label.setToolTip(
            f"{QCoreApplication.translate('MainWindow', 'Arbeitsverzeichnis', None)}: {self._current_raw_work_dir}\n"
            f"{QCoreApplication.translate('MainWindow', 'Klicken zum Öffnen', None)}"
        )

    def _handle_open_workdir_request(self, event=None): # event can be None if called from action
        """Requests the controller to open the current working directory."""
        # We'll get the actual path from the controller or config manager later
        # For now, this just signals the intent.
        if self.controller:
            self.controller.open_working_directory()
        else:
            self.logger.warning("Controller not available to open working directory.")

    def showEvent(self, event: QShowEvent):
        """Handle the show event, ensuring the workdir label is updated after layout."""
        super().showEvent(event)
        # After the window is shown, the layout should have been applied.
        # Re-update the label to ensure eliding uses the correct width.
        if self._current_raw_work_dir:
            # Call update_workdir_label directly as path is already stored
            self.update_workdir_label(self._current_raw_work_dir)

    def resizeEvent(self, event: QResizeEvent):
        """Handle the resize event, ensuring the workdir label is updated."""
        super().resizeEvent(event)
        # When the window is resized, update the elided path.
        if self._current_raw_work_dir and self.workdir_label.isVisible():
            self.update_workdir_label(self._current_raw_work_dir)

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
