from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QFrame, QSplashScreen, QLabel, QVBoxLayout
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QTimer, QThreadPool, Qt
from PySide6.QtUiTools import QUiLoader
import sys
import signal
import logging
import os
from pathlib import Path

# For macOS foreground activation
if sys.platform == "darwin":
    try:
        from Cocoa import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
    except ImportError:
        logging.getLogger("AIDocSynth").error("pyobjc not installed, skipping macOS-specific activation.")
        # Define a dummy class to avoid NameError later
        class NSRunningApplication:
            @staticmethod
            def currentApplication(): return None

# Wichtig: Importiert die kompilierten Ressourcen (Icons, etc.)
from .ui import qrc_resources
from .ui.main_window_view import MainWindowView
from .ui.settings_dialog_view import SettingsDialogView
from .controllers.main_controller import MainController
from .controllers.settings_controller import SettingsController
from .utils.worker import Worker
from .services.ocr_service import initialize_ocr

def setup_tray_icon(parent_app):
    """Creates and sets up the system tray icon."""
    # Load the icon from the file system to bypass potential resource system issues.
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        base_path = sys._MEIPASS
        icon_path = os.path.join(base_path, 'aidocsynth', 'ui', 'resources', 'app.png')
    else:
        # Running in a normal Python environment
        script_dir = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(script_dir, "ui", "resources", "app.png")
    
    icon = QIcon(icon_path)
    if icon.isNull():
        logging.getLogger("AIDocSynth").error(f"Failed to load tray icon from path: {icon_path}")
        return None

    tray_icon = QSystemTrayIcon(icon, parent_app)
    tray_menu = QMenu()

    # Add 'About' option
    if hasattr(parent_app, 'main_controller') and hasattr(parent_app.main_controller, 'show_about_dialog'):
        about_action = tray_menu.addAction("Über AIDocSynth")
        about_action.triggered.connect(parent_app.main_controller.show_about_dialog)
        tray_menu.addSeparator()

    if hasattr(parent_app, 'settings_dialog'):
        tray_menu.addAction("Einstellungen", parent_app.settings_dialog.show)
        tray_menu.addSeparator()
    tray_menu.addAction("Beenden", parent_app.quit)
    tray_icon.setContextMenu(tray_menu)

    def on_tray_activated(reason):
        # Show the window on left-click
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            main_win = QApplication.instance().main_window
            if main_win:
                main_win.show()
                main_win.raise_()
                main_win.activateWindow()

    tray_icon.activated.connect(on_tray_activated)

    tray_icon.show()
    return tray_icon

def load_main_application(splash):
    """
    Loads the main UI, initializes services, and sets up the main window.
    This function is called after the splash screen is visible.
    """

    # Load the main window UI
    loader = QUiLoader()
    # Create the main controller
    ctrl = MainController()

    # Create the main window view and pass the controller to it
    win = MainWindowView(controller=ctrl)
    
    # Keep references to the main window and controller on the app instance to
    # prevent them from being garbage collected.
    app = QApplication.instance()
    app.main_window = win
    app.main_controller = ctrl

    # Initialize Settings Dialog and Controller
    # The controller will manage the dialog's logic (e.g., provider switching)
    dlgSettings = SettingsDialogView(win)
    SettingsController(dlgSettings)
    app.settings_dialog = dlgSettings

    # Function to show the main window and close the splash screen
    def show_main_window():
        nonlocal win, splash
        splash.finish(win)
        win.show()
        win.raise_()
        win.activateWindow()

    # Show the main window and close the splash screen.
    show_main_window()

    # Setup Tray Icon, parented to the application itself to ensure correct lifetime.
    app = QApplication.instance() # app should already be defined, but re-assigning is fine.
    app.tray_icon = setup_tray_icon(app)

    # --- OCR Worker Setup --- 
    # Callbacks for the OCR worker. These will update the status bar of the
    # already visible main window.
    def on_worker_finished():
        # Signal that OCR is ready
        # Main window is already shown and splash is closed.
        if QApplication.instance() and QApplication.instance().main_controller:
            QApplication.instance().main_controller.ocr_status_changed.emit("Ready")

    def on_worker_error(error_message):
        # Splash is already closed. Main window is visible.
        logging.getLogger("AIDocSynth.OCRWorker").error(f"Worker Error: {error_message}")
        if QApplication.instance() and QApplication.instance().main_controller:
            QApplication.instance().main_controller.ocr_status_changed.emit(f"OCR Error: {error_message}")
        # No splash interaction here. The error is reported in the status bar.

    # OCR Initialization (runs in background, updates status bar of already visible window)
    # The initial status "Initializing OCR engine..." will be emitted by initialize_ocr itself.
    # 'ctrl' is the MainController instance, available in this scope from earlier UI setup.
    
    pool = QThreadPool.globalInstance()
    worker = Worker(initialize_ocr)
    
    # Connect signals. These callbacks now only update the status bar
    # as the main window is already visible and splash is closed.
    worker.sig.finished.connect(on_worker_finished)
    worker.sig.error.connect(on_worker_error)
    # 'ctrl' is the MainController, its ocr_status_changed signal is connected to the UI.
    worker.sig.progress_updated.connect(ctrl.ocr_status_changed.emit)

    # Keep a reference to the worker.
    # 'QApplication.instance().main_window' was set by show_main_window or earlier UI setup.
    if QApplication.instance() and QApplication.instance().main_window:
        QApplication.instance().main_window.worker = worker
    
    pool.start(worker)

def main():
    """
    Main entry point: sets up the app and splash screen, then hands off to the
    main loading function via a timer to ensure the splash screen is shown first.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("AIDocSynth") # Used by AboutDialog and macOS menu
    app.setApplicationDisplayName("AI Doc Synth") # Used by AboutDialog
    app.setApplicationVersion("0.1.0") # Used by AboutDialog
    app.setOrganizationName("tobit0101") # Used by AboutDialog for copyright
    app.setQuitOnLastWindowClosed(False)

    # On macOS, force the application to the foreground to ensure the splash screen is visible.
    if sys.platform == "darwin" and NSRunningApplication.currentApplication() is not None:
        def force_foreground():
            NSRunningApplication.currentApplication().activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        QTimer.singleShot(0, force_foreground)

    # Setup and show splash screen immediately
    # Load the splash screen image from the file system instead of resources
    # This avoids bloating the qrc resource file with large images.
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        base_path = sys._MEIPASS
        splash_image_path = os.path.join(base_path, 'aidocsynth', 'ui', 'resources', 'AIDocSynth_Illustration.png')
    else:
        # Running in a normal Python environment
        script_dir = os.path.dirname(os.path.realpath(__file__))
        splash_image_path = os.path.join(script_dir, "ui", "resources", "AIDocSynth_Illustration.png")
    pixmap = QPixmap(splash_image_path)

    # Scale pixmap if its height exceeds 500px, keeping aspect ratio
    if pixmap.height() > 500:
        pixmap = pixmap.scaledToHeight(500, Qt.SmoothTransformation)

    splash = QSplashScreen(pixmap)
    try:
        splash.show()
        splash.raise_()
        splash.activateWindow()
        QApplication.processEvents()
        splash.showMessage("Loading UI...", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
        QApplication.processEvents() # Ensure "Loading UI..." message is displayed
    except Exception as e:
        logging.getLogger("AIDocSynth.Splash").error(f"Error during splash screen setup: {e}", exc_info=True)

    # Ensure that the application quits when Ctrl+C is pressed.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger("AIDocSynth")
    logger.info("Application starting...")

    # Use a timer to delay loading. This allows the event loop to process and
    # display the splash screen before we start time-consuming operations.
    QTimer.singleShot(100, lambda: load_main_application(splash))

    logger.info("Starting Qt event loop.")
    exit_code = app.exec()
    logger.info(f"Application finished with exit code {exit_code}.")
    sys.exit(exit_code)
