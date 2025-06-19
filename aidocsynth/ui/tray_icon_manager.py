import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QCursor

def setup_tray_icon(parent_app):
    """Creates and sets up the system tray icon."""
    # Load the icon from the file system to bypass potential resource system issues.
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        base_path = sys._MEIPASS  # sys._MEIPASS is the root of the extracted bundle
        icon_path = os.path.join(base_path, 'aidocsynth', 'ui', 'resources', 'app_tray.png')
    else:
        # Running in a normal Python environment
        # __file__ will be .../AIDocSynth/aidocsynth/ui/tray_icon_manager.py
        # We need to go up one level from 'ui' to get to the 'resources' folder correctly
        script_dir = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(script_dir, "resources", "app_tray.png")
    
    icon = QIcon(icon_path)
    if icon.isNull():
        logging.getLogger("AIDocSynth.TrayManager").error(f"Failed to load tray icon from path: {icon_path}")
        return None

    tray_icon = QSystemTrayIcon(icon, parent_app)
    tray_menu = QMenu()
    main_win = parent_app.main_window # Get main_window instance

    # 1. Öffnen (Open)
    if main_win:  # Ensure main_win exists to connect its show_and_raise method
        open_action = tray_menu.addAction("Öffnen")
        open_action.triggered.connect(main_win.show_and_raise)

    # 2. Einstellungen (Settings)
    if hasattr(parent_app, 'settings_dialog'):
        tray_menu.addAction("Einstellung", parent_app.settings_dialog.show)
    
    tray_menu.addSeparator() # Separator after "Über"

    # 4. Beenden (Exit)
    tray_menu.addAction("Beenden", parent_app.quit)

    # For macOS, we'll show the menu manually on Context activation
    # to prevent it from showing on a standard (Trigger) click.
    if sys.platform != "darwin":
        tray_icon.setContextMenu(tray_menu)

    def on_tray_activated(reason):
        main_win = QApplication.instance().main_window
        if not main_win:
            return

        # 'tray_icon' is captured from the outer scope of setup_tray_icon
        
        if sys.platform == "win32":
            if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left-click
                main_win.show_and_raise()
            # For right-click (Context), QSystemTrayIcon shows the menu automatically.
        elif sys.platform == "darwin":
            if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left-click
                main_win.show_and_raise()
            elif reason == QSystemTrayIcon.ActivationReason.Context:  # Ctrl-click
                # On macOS, show the tray_menu (from outer scope) manually,
                # as it's not set via setContextMenu.
                if tray_menu:
                    tray_menu.popup(QCursor.pos())
        else:  # Fallback for other platforms (e.g., Linux)
            if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left-click
                main_win.show_and_raise()
            elif reason == QSystemTrayIcon.ActivationReason.Context:  # Right-click
                if tray_icon.contextMenu():
                    tray_icon.contextMenu().popup(QCursor.pos())

    tray_icon.activated.connect(on_tray_activated)

    tray_icon.show()
    return tray_icon
