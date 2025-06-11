from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QFrame, QSplashScreen, QLabel, QVBoxLayout
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QTimer, QThreadPool, Qt
from PySide6.QtUiTools import QUiLoader
import sys
import time
import os
from pathlib import Path

# Wichtig: Importiert die kompilierten Ressourcen (Icons, etc.)
from .ui import qrc_resources
from .ui.main_window_view import MainWindowView
from .controllers.main_controller import MainController
from .utils.worker import Worker
from .services.ocr_service import initialize_ocr

def setup_tray_icon(parent_app):
    """Creates and sets up the system tray icon."""
    # Load the icon from the file system to bypass potential resource system issues.
    script_dir = os.path.dirname(os.path.realpath(__file__))
    icon_path = os.path.join(script_dir, "ui", "resources", "app.png")
    
    icon = QIcon(icon_path)
    if icon.isNull():
        print(f"Failed to load tray icon from path: {icon_path}", file=sys.stderr)
        return None

    tray_icon = QSystemTrayIcon(icon, parent_app)
    tray_menu = QMenu()
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

    # Function to show the main window and close the splash screen
    def show_main_window():
        nonlocal win, splash
        splash.finish(win)
        win.show()
        win.raise_()
        win.activateWindow()

        # Setup Tray Icon, parented to the application itself to ensure correct lifetime.
        app = QApplication.instance()
        app.tray_icon = setup_tray_icon(app)

    # This function ensures the splash is shown for a fixed delay after loading.
    def on_worker_finished():
        # Signal that OCR is ready
        QApplication.instance().main_controller.ocr_status_changed.emit("Ready")
        
        # Always wait a fixed amount of time after loading is complete.
        fixed_delay_ms = 1500 # 1.5 seconds
        QTimer.singleShot(fixed_delay_ms, show_main_window)

    # In parallel, initialize the OCR model.
    splash.showMessage("Initializing OCR Model...", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
    pool = QThreadPool.globalInstance()
    worker = Worker(initialize_ocr)
    worker.sig.finished.connect(on_worker_finished)

    # Emit initial status
    ctrl.ocr_status_changed.emit("Initializing OCR model...")

    # Keep a reference to the worker to prevent it from being garbage collected
    # while the thread is running. This is a common pitfall in Qt+Python.
    QApplication.instance().main_window.worker = worker

    pool.start(worker)

def main():
    """
    Main entry point: sets up the app and splash screen, then hands off to the
    main loading function via a timer to ensure the splash screen is shown first.
    """
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Setup and show splash screen immediately
    # Load the splash screen image from the file system instead of resources
    # This avoids bloating the qrc resource file with large images.
    script_dir = os.path.dirname(os.path.realpath(__file__))
    splash_image_path = os.path.join(script_dir, "ui", "resources", "AIDocSynth_Illustration.png")
    pixmap = QPixmap(splash_image_path)
    splash = QSplashScreen(pixmap)
    splash.show()
    splash.raise_()
    splash.activateWindow()
    QApplication.processEvents()
    splash.showMessage("Loading UI...", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)

    # Use a timer to delay loading. This allows the event loop to process and
    # display the splash screen before we start time-consuming operations.
    QTimer.singleShot(100, lambda: load_main_application(splash))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
