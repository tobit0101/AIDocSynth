from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtCore import QTimer, QThreadPool
import sys
import signal
import logging
import os
import time
import asyncio
from logging.handlers import RotatingFileHandler
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
from .services.settings_service import settings
from .controllers.settings_controller import SettingsController
from .utils.worker import Worker
from .ui.tray_icon_manager import setup_tray_icon # Import from new module

def load_main_application(splash):
    """
    Loads the main UI, initializes services, and sets up the main window.
    This function is called after the main window is visible.
    """
    # --- Lazy Import --- 
    from .services.ocr_service import initialize_ocr

    # Keep references to the main window and controller on the app instance to
    # prevent them from being garbage collected.
    app = QApplication.instance()
    # app.main_window and app.main_controller are now set in main()

    # Initialize Settings Dialog and Controller
    # The controller will manage the dialog's logic (e.g., provider switching)
    dlgSettings = SettingsDialogView(app.main_window) # Use app.main_window
    SettingsController(dlgSettings)
    app.settings_dialog = dlgSettings

    # Setup Tray Icon, parented to the application itself to ensure correct lifetime.
    app.tray_icon = setup_tray_icon(app)

    # --- OCR Worker Setup --- 
    # Callbacks for the OCR worker. These will update the status bar of the
    # already visible main window.
    def on_worker_finished():
        # This is now handled by the signal from within the worker itself ("Bereit")
        # so this explicit signal is no longer needed and causes conflicts.
        pass

    def on_worker_error(error_message):
        logging.getLogger("AIDocSynth.OCRWorker").error(f"Worker Error: {error_message}")
        if QApplication.instance() and QApplication.instance().main_controller:
            QApplication.instance().main_controller.ocr_status_changed.emit(f"OCR Error: {error_message}")

    # OCR Initialization (runs in background, updates status bar of already visible window)
    pool = QThreadPool.globalInstance()
    # Get MainController from app instance
    main_ctrl = QApplication.instance().main_controller
    worker = Worker(initialize_ocr)
    
    worker.sig.finished.connect(on_worker_finished)
    worker.sig.error.connect(on_worker_error)
    worker.sig.progress_updated.connect(main_ctrl.ocr_status_changed.emit)

    # Keep a reference to the worker on the main_window instance.
    if QApplication.instance() and QApplication.instance().main_window:
        QApplication.instance().main_window.worker = worker
    
    pool.start(worker)

def setup_logging(level="INFO"):
    """Configures the root logger for console and file output."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Basis-Ordner für Logs definieren
    log_dir = Path.home() / ".config" / "AIDocSynth" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File Handler (max 5 MB, behält die letzten 3 Dateien)
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Basic Config mit beiden Handlern
    logging.basicConfig(level=log_level, handlers=[file_handler, console_handler])
    
    logger = logging.getLogger("AIDocSynth")
    logger.info(f"Logging initialized. App-Log: {log_file}")
    return logger


def main(loglevel="INFO"):
    """
    Main entry point: sets up the app, shows the main window immediately,
    and defers other initializations.
    """
    t0 = time.perf_counter()

    app = QApplication(sys.argv)
    app.setApplicationName("AIDocSynth")
    app.setApplicationDisplayName("AI Doc Synth")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("tobit0101")
    app.setQuitOnLastWindowClosed(False)

    # Setup basic logging early
    logger = setup_logging(level=loglevel)
    logger.info("Application starting...")

    # Ensure that the application quits when Ctrl+C is pressed.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # On macOS, force the application to the foreground.
    if sys.platform == "darwin" and NSRunningApplication.currentApplication() is not None:
        def force_foreground():
            NSRunningApplication.currentApplication().activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        QTimer.singleShot(0, force_foreground) # Run after event loop starts

    # --- Main UI Setup --- 
    # Import services and models needed for dependency injection.
    from .services.settings_service import settings

    # --- Main UI Setup --- 
    # Create the main window view. The controller will be set later.
    main_window = MainWindowView(controller=None)

    # Create the main controller, injecting the necessary dependencies, including the view.
    main_controller = MainController(
        config_manager=settings,
        view=main_window
    )
    
    # Now, assign the created controller back to the view.
    main_window.controller = main_controller

    # Connect signals that depend on the controller.
    main_window.connect_controller_signals()
    
    # Keep references on the app instance
    app.main_window = main_window
    app.main_controller = main_controller

    def cleanup():
        """Clean up resources."""
        logging.info("Starting application cleanup...")
        app.main_controller.close()



        if app.tray_icon:
            app.tray_icon.hide()
        logging.info("Application cleanup finished.")

    # Show main window immediately
    logger.info("Showing main window.")
    main_window.show()
    main_window.raise_()
    main_window.activateWindow()
    QApplication.processEvents() # Ensure window is drawn before deferred tasks
    logger.info(f"Main window visible after {time.perf_counter() - t0:.3f} seconds.")

    # --- Deferred Initializations --- 
    # Use a timer to delay non-critical loading. This allows the event loop 
    # to process and display the main window before these operations.
    # The 'load_main_application' function is now repurposed for these deferred tasks.
    # It no longer handles splash screen or initial window showing.
    QTimer.singleShot(0, lambda: load_main_application(None)) # Pass None as splash is removed

    # --- Graceful Shutdown ---
    # Ensure the process pool is closed when the application quits.
    app.aboutToQuit.connect(cleanup)

    logger.info("Starting Qt event loop.")
    exit_code = app.exec()
    logger.info(f"Application finished with exit code {exit_code}.")
    sys.exit(exit_code)
